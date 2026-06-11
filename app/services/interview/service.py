import json
from typing import Generator

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.entities import InterviewMessage, InterviewSession, Job, Resume, ScreeningResult
from app.schemas.resume_structured import FollowupPack, QuestionPack, ResumeStructured
from app.services.interview.nodes import (
    InterviewGraphState,
    closing_node,
    evaluate_answer_node,
    init_persona_node,
    stream_opening,
    stream_question,
)
from app.services.interview.report import compress_conversation_summary, generate_interview_report


class InterviewService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def start_session(self, job_id: int, resume_id: int, persona: str) -> InterviewSession:
        job = self.db.get(Job, job_id)
        resume = self.db.get(Resume, resume_id)
        if not job or not resume or resume.job_id != job_id:
            raise ValueError("Invalid job_id or resume_id")

        session = InterviewSession(
            job_id=job_id,
            resume_id=resume_id,
            persona=persona,
            status="active",
            pending_action="stream_opening",
        )
        self.db.add(session)
        self.db.flush()

        state = self._build_state(session, job, resume)
        result = init_persona_node(state)
        a_layer_brief = self._build_a_layer_brief(job.id, resume.id)

        session.persona_prompt = (result.get("persona_prompt") or "") + "\n\n" + a_layer_brief
        session.pending_action = "stream_opening"
        session.round_count = 0
        self.db.commit()
        self.db.refresh(session)
        return session

    def submit_answer(self, session_id: int, content: str) -> InterviewSession:
        session = self._get_active_session(session_id)
        job = self.db.get(Job, session.job_id)
        resume = self.db.get(Resume, session.resume_id)
        if not job or not resume:
            raise ValueError("Session data missing")

        self._save_message(session.id, "user", content)
        state = self._build_state(session, job, resume)
        state["last_user_message"] = content

        eval_result = evaluate_answer_node(state)
        session.round_count = eval_result["round_count"]
        session.topics_covered_json = json.dumps(
            eval_result.get("topics_covered", []), ensure_ascii=False
        )
        session.last_evaluation_json = json.dumps(
            eval_result.get("last_evaluation", {}), ensure_ascii=False
        )

        if eval_result["round_count"] % 3 == 0:
            messages = self._load_messages(session.id)
            session.running_summary = compress_conversation_summary(
                messages, session.running_summary or ""
            )

        if eval_result.get("next_action") == "closing":
            session.pending_action = "stream_closing"
        else:
            session.pending_action = "stream_question"

        self.db.commit()
        self.db.refresh(session)
        return session

    def stream_pending(self, session_id: int) -> Generator[str, None, None]:
        session = self.db.get(InterviewSession, session_id)
        if not session:
            raise ValueError("Session not found")

        job = self.db.get(Job, session.job_id)
        resume = self.db.get(Resume, session.resume_id)
        if not job or not resume:
            raise ValueError("Session data missing")

        action = session.pending_action
        if action == "stream_opening":
            state = self._build_state(session, job, resume)
            full = ""
            for chunk in stream_opening(state):
                full += chunk
                yield chunk
            self._save_message(session.id, "assistant", full)
            session.pending_action = "wait_answer"
            self.db.commit()
            return

        if action == "stream_question":
            state = self._build_state(session, job, resume)
            if session.last_evaluation_json:
                state["last_evaluation"] = json.loads(session.last_evaluation_json)
            full = ""
            for chunk in stream_question(state):
                full += chunk
                yield chunk
            self._save_message(session.id, "assistant", full)
            session.pending_action = "wait_answer"
            self.db.commit()
            return

        if action == "stream_closing":
            state = self._build_state(session, job, resume)
            close_result = closing_node(state)
            text = close_result["assistant_reply"]
            for i in range(0, len(text), 8):
                yield text[i : i + 8]
            self._save_message(session.id, "assistant", text)
            session.pending_action = "generate_report"
            self.db.commit()
            return

        if action == "wait_answer":
            yield ""
            return

        yield ""

    def end_session(self, session_id: int) -> InterviewSession:
        session = self.db.get(InterviewSession, session_id)
        if not session:
            raise ValueError("Session not found")
        if session.status == "completed" and session.report_json:
            return session

        job = self.db.get(Job, session.job_id)
        resume = self.db.get(Resume, session.resume_id)
        if not job or not resume:
            raise ValueError("Session data missing")

        if session.pending_action != "generate_report":
            state = self._build_state(session, job, resume)
            close_result = closing_node(state)
            self._save_message(session.id, "assistant", close_result["assistant_reply"])

        messages = self._load_messages(session.id)
        structured = self._parse_structured(resume)
        risk_notes = []
        if session.last_evaluation_json:
            ev = json.loads(session.last_evaluation_json)
            if ev.get("resume_mismatch"):
                risk_notes.append(ev.get("notes", "Resume mismatch detected"))

        report = generate_interview_report(
            job.raw_text,
            structured.model_dump(),
            messages,
            risk_notes,
        )
        session.report_json = report.model_dump_json(ensure_ascii=False)
        session.status = "completed"
        session.pending_action = None
        self._apply_feedback_loop(resume, report)
        self.db.commit()
        self.db.refresh(session)
        return session

    def _apply_feedback_loop(self, resume: Resume, report) -> None:
        if resume.structured_json:
            try:
                data = json.loads(resume.structured_json)
                gaps = report.next_round_focus[:3]
                notes = data.get("interview_feedback", [])
                notes.extend(gaps)
                data["interview_feedback"] = notes[-5:]
                resume.structured_json = json.dumps(data, ensure_ascii=False)
            except Exception:
                pass

    def _get_active_session(self, session_id: int) -> InterviewSession:
        session = self.db.get(InterviewSession, session_id)
        if not session:
            raise ValueError("Session not found")
        if session.status != "active":
            raise ValueError("Interview session is not active")
        if session.pending_action != "wait_answer":
            raise ValueError("Please wait for the interviewer question before answering")
        return session

    def _build_state(
        self, session: InterviewSession, job: Job, resume: Resume
    ) -> InterviewGraphState:
        structured = self._parse_structured(resume)
        messages = self._load_messages(session.id)
        a_layer_brief = self._build_a_layer_brief(job.id, resume.id)
        return InterviewGraphState(
            job_text=job.raw_text,
            resume_text=resume.raw_text,
            structured=structured.model_dump(),
            persona=session.persona,
            persona_prompt=session.persona_prompt or "",
            running_summary=session.running_summary or "",
            round_count=session.round_count,
            max_rounds=self.settings.max_interview_rounds,
            messages=messages,
            topics_covered=json.loads(session.topics_covered_json or "[]"),
            risk_notes=[],
            a_layer_context=a_layer_brief,
        )

    def _build_a_layer_brief(self, job_id: int, resume_id: int) -> str:
        screening = (
            self.db.query(ScreeningResult)
            .filter(
                ScreeningResult.job_id == job_id,
                ScreeningResult.resume_id == resume_id,
            )
            .first()
        )
        if not screening:
            return "A-layer screening: no prior screening data."

        lines = ["=== A-layer screening seeds (priority for early interview rounds) ==="]
        gaps = json.loads(screening.gaps_json or "[]")
        if gaps:
            lines.append("Known gaps: " + "; ".join(gaps[:5]))

        try:
            followups = FollowupPack.model_validate_json(
                screening.followups_json or '{"items":[]}'
            ).items
            if followups:
                lines.append("Priority follow-up questions:")
                for i, f in enumerate(followups[:5], 1):
                    lines.append(f"{i}. {f.question} (intent: {f.probe_intent})")
        except Exception:
            pass

        if screening.questions_json:
            try:
                questions = QuestionPack.model_validate_json(screening.questions_json).items
                competencies = [q.competency for q in questions[:10] if q.competency]
                if competencies:
                    lines.append(
                        "Question pack competencies to cover: " + ", ".join(competencies[:10])
                    )
            except Exception:
                pass

        if screening.decision_summary:
            lines.append(f"Screening decision: {screening.decision_summary}")

        return "\n".join(lines)

    def _parse_structured(self, resume: Resume) -> ResumeStructured:
        if resume.structured_json:
            try:
                return ResumeStructured.model_validate_json(resume.structured_json)
            except Exception:
                pass
        return ResumeStructured(summary=resume.raw_text[:500])

    def _load_messages(self, session_id: int) -> list[dict[str, str]]:
        rows = (
            self.db.query(InterviewMessage)
            .filter(InterviewMessage.session_id == session_id)
            .order_by(InterviewMessage.id)
            .all()
        )
        return [{"role": r.role, "content": r.content} for r in rows]

    def _save_message(self, session_id: int, role: str, content: str) -> None:
        self.db.add(
            InterviewMessage(session_id=session_id, role=role, content=content)
        )
        self.db.flush()
