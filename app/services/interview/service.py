import json
from datetime import datetime, timezone
from typing import Callable, Generator

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.entities import InterviewMessage, InterviewSession, Job, Resume, ScreeningResult
from app.schemas.resume_structured import (
    CandidateInterviewFeedback,
    FollowupPack,
    InterviewConfig,
    JDStructured,
    LiveAssessment,
    QuestionPack,
    ResumeStructured,
)
from app.services.interview.config import resolve_interview_config
from app.services.interview.nodes import (
    InterviewGraphState,
    build_init_graph,
    build_post_answer_graph,
    closing_node,
    stream_encouragement,
    stream_followup,
    stream_opening,
    stream_question,
)
from app.services.interview.input_guard import check_input
from app.services.interview.stream_guard import StreamKind, ensure_stream_output
from app.services.interview.report import compress_conversation_summary, generate_interview_report
from app.services.job_templates import infer_template_id, load_template
from app.services.rubric_parser import rubric_to_context

_init_graph = build_init_graph()
_post_answer_graph = build_post_answer_graph()


class InterviewService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def start_session(
        self,
        job_id: int,
        resume_id: int,
        persona: str,
        config: InterviewConfig | None = None,
    ) -> InterviewSession:
        job = self.db.get(Job, job_id)
        resume = self.db.get(Resume, resume_id)
        if not job or not resume or resume.job_id != job_id:
            raise ValueError("Invalid job_id or resume_id")

        interview_config = resolve_interview_config(persona, config)
        competencies_planned, followup_queue = self._load_a_layer_seeds(job.id, resume.id, job)
        question_queue = self._load_question_queue(
            job.id, resume.id, job, competencies_planned, interview_config
        )
        template = load_template(job.template_id) or load_template(
            infer_template_id(job.title, job.raw_text)
        )
        if template and not competencies_planned:
            competencies_planned = template.default_competencies[:12]
        if template and not job.template_id:
            job.template_id = template.id

        competency_status = {c: "uncovered" for c in competencies_planned if c}

        session = InterviewSession(
            job_id=job_id,
            resume_id=resume_id,
            persona=interview_config.persona,
            status="active",
            pending_action="stream_opening",
            phase="opening",
            competencies_planned_json=json.dumps(competencies_planned, ensure_ascii=False),
            followup_queue_json=json.dumps(followup_queue, ensure_ascii=False),
            competency_status_json=json.dumps(competency_status, ensure_ascii=False),
            interview_config_json=interview_config.model_dump_json(ensure_ascii=False),
            question_queue_json=json.dumps(question_queue, ensure_ascii=False),
            question_index=0,
            encouraged_this_round=False,
        )
        self.db.add(session)
        self.db.flush()

        state = self._build_state(session, job, resume)
        result = _init_graph.invoke(state)
        a_layer_brief = self._build_a_layer_brief(job.id, resume.id)
        flywheel = self._build_candidate_experience_flywheel(job.id)

        session.persona_prompt = (result.get("persona_prompt") or "") + "\n\n" + a_layer_brief
        if flywheel:
            session.persona_prompt += "\n\n" + flywheel
        session.pending_action = "stream_opening"
        session.round_count = 0
        session.phase = "opening"
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

        guard = check_input(content)
        if guard.blocked:
            state["input_guard_blocked"] = True
            state["guard_threat_type"] = guard.threat_type
            state["guard_reason"] = guard.reason

        result = _post_answer_graph.invoke(state, config={"recursion_limit": 8})
        self._persist_state(session, result)

        if result.get("round_count", 0) % 3 == 0:
            messages = self._load_messages(session.id)
            session.running_summary = compress_conversation_summary(
                messages, session.running_summary or ""
            )

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
        state = self._build_state(session, job, resume)

        if action == "stream_opening":
            full = yield from self._yield_guarded_stream(
                state, stream_opening, kind="opening"
            )
            self._save_message(session.id, "assistant", full)
            session.pending_action = "wait_answer"
            session.phase = "opening"
            self.db.commit()
            return

        if action == "stream_followup":
            full = yield from self._yield_guarded_stream(
                state, stream_followup, kind="followup"
            )
            self._save_message(session.id, "assistant", full)
            session.pending_action = "wait_answer"
            if not session.current_topic:
                session.current_topic = InterviewService._last_assistant_from_messages(
                    self._load_messages(session.id)
                )
            self.db.commit()
            return

        if action == "stream_encouragement":
            full = ""
            for chunk in stream_encouragement(state):
                full += chunk
                yield chunk
            self._save_message(session.id, "assistant", full)
            session.pending_action = "wait_answer"
            session.encouraged_this_round = True
            self.db.commit()
            return

        if action == "stream_question":
            full = yield from self._yield_guarded_stream(
                state, stream_question, kind="question"
            )
            self._save_message(session.id, "assistant", full)
            session.pending_action = "wait_answer"
            plan = json.loads(session.topic_plan_json or "{}")
            target = plan.get("competency_target", "")
            session.current_topic = plan.get("next_topic") or target or session.current_topic
            if target:
                status = json.loads(session.competency_status_json or "{}")
                if target not in status:
                    status[target] = "uncovered"
                session.competency_status_json = json.dumps(status, ensure_ascii=False)
                covered = json.loads(session.competencies_covered_json or "[]")
                if target not in covered:
                    covered.append(target)
                    session.competencies_covered_json = json.dumps(covered, ensure_ascii=False)
            config = {}
            if session.interview_config_json:
                try:
                    config = json.loads(session.interview_config_json)
                except Exception:
                    pass
            if config.get("interview_mode") == "standardized":
                session.question_index = (session.question_index or 0) + 1
            self.db.commit()
            return

        if action == "stream_closing":
            close_result = closing_node(state)
            text = close_result["assistant_reply"]
            for i in range(0, len(text), 8):
                yield text[i : i + 8]
            self._save_message(session.id, "assistant", text)
            session.pending_action = "generate_report"
            session.phase = "closing"
            self.db.commit()
            return

        if action == "wait_answer":
            yield ""
            return

        yield ""

    def _yield_guarded_stream(
        self,
        state: InterviewGraphState,
        stream_fn: Callable[[InterviewGraphState], Generator[str, None, None]],
        *,
        kind: StreamKind,
    ) -> Generator[str, None, str]:
        raw = "".join(stream_fn(state))
        persona = str(state.get("persona") or "tech_lead")

        if self.settings.stream_guard_enabled:
            result = ensure_stream_output(raw, kind=kind, persona=persona, state=state)
            text = result.text
        else:
            text = raw

        chunk_size = 8
        for i in range(0, len(text), chunk_size):
            yield text[i : i + chunk_size]
        return text

    def prepare_end_session(self, session_id: int) -> InterviewSession:
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

        session.status = "generating_report"
        session.pending_action = "report_queued"
        self.db.commit()
        self.db.refresh(session)

        from app.services.report_async import start_report_generation

        start_report_generation(session_id)
        return session

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
        risk_notes = json.loads(session.risk_notes_json or "[]")
        evaluations_log = json.loads(session.evaluations_log_json or "[]")
        live = None
        if session.live_assessment_json:
            try:
                live = json.loads(session.live_assessment_json)
            except Exception:
                pass

        report = generate_interview_report(
            job.raw_text,
            structured.model_dump(),
            messages,
            risk_notes,
            evaluations_log=evaluations_log,
            live_assessment=live,
            rubric_context=self._rubric_context(job),
        )
        session.report_json = report.model_dump_json(ensure_ascii=False)
        session.status = "completed"
        session.pending_action = "completed"
        self._apply_feedback_loop(resume, report, session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_live_assessment(self, session_id: int) -> LiveAssessment | None:
        session = self.db.get(InterviewSession, session_id)
        if not session or not session.live_assessment_json:
            return None
        return LiveAssessment.model_validate_json(session.live_assessment_json)

    def submit_candidate_feedback(
        self, session_id: int, rating: int, comment: str = ""
    ) -> dict:
        session = self.db.get(InterviewSession, session_id)
        if not session:
            raise ValueError("Session not found")
        if session.status != "completed" or not session.report_json:
            raise ValueError("请先完成面试并生成报告")
        if session.candidate_feedback_json:
            raise ValueError("Feedback already submitted")

        feedback = CandidateInterviewFeedback(
            rating=rating,
            comment=(comment or "")[:500],
            submitted_at=datetime.now(timezone.utc).isoformat(),
        )
        session.candidate_feedback_json = feedback.model_dump_json(ensure_ascii=False)
        self.db.commit()
        self.db.refresh(session)
        return feedback.model_dump()

    @staticmethod
    def parse_candidate_feedback(session: InterviewSession) -> dict | None:
        if not session.candidate_feedback_json:
            return None
        try:
            return json.loads(session.candidate_feedback_json)
        except Exception:
            return None

    def get_status(self, session_id: int) -> dict:
        session = self.db.get(InterviewSession, session_id)
        if not session:
            raise ValueError("Session not found")
        config = {}
        if session.interview_config_json:
            try:
                config = json.loads(session.interview_config_json)
            except Exception:
                pass
        question_queue = json.loads(session.question_queue_json or "[]")
        q_index = session.question_index or 0
        upcoming: list[dict] = []
        for raw in question_queue[q_index : q_index + 3]:
            if isinstance(raw, dict):
                upcoming.append(
                    {
                        "question": raw.get("question", ""),
                        "competency": raw.get("competency", ""),
                        "difficulty": raw.get("difficulty", ""),
                        "category": raw.get("category", ""),
                    }
                )
            elif isinstance(raw, str):
                upcoming.append({"question": raw, "competency": "", "difficulty": "", "category": ""})
        return {
            "session_id": session.id,
            "job_id": session.job_id,
            "status": session.status,
            "phase": session.phase,
            "round_count": session.round_count,
            "pending_action": session.pending_action,
            "competencies_covered": json.loads(session.competencies_covered_json or "[]"),
            "competencies_planned": json.loads(session.competencies_planned_json or "[]"),
            "competency_status": json.loads(session.competency_status_json or "{}"),
            "followup_streak": session.followup_streak,
            "interview_mode": config.get("interview_mode", "adaptive"),
            "interview_config": config,
            "question_index": session.question_index,
            "current_topic": session.current_topic or "",
            "followup_queue": json.loads(session.followup_queue_json or "[]"),
            "upcoming_questions": upcoming,
        }

    def get_messages(self, session_id: int) -> list[dict[str, str]]:
        session = self.db.get(InterviewSession, session_id)
        if not session:
            raise ValueError("Session not found")
        return self._load_messages(session_id)

    def _persist_state(self, session: InterviewSession, state: InterviewGraphState) -> None:
        session.round_count = state.get("round_count", session.round_count)
        session.phase = state.get("phase", session.phase)
        session.topics_covered_json = json.dumps(
            state.get("topics_covered", []), ensure_ascii=False
        )
        session.last_evaluation_json = json.dumps(
            state.get("last_evaluation", {}), ensure_ascii=False
        )
        session.risk_notes_json = json.dumps(state.get("risk_notes", []), ensure_ascii=False)
        session.evaluations_log_json = json.dumps(
            state.get("evaluations_log", []), ensure_ascii=False
        )
        session.competencies_covered_json = json.dumps(
            state.get("competencies_covered", []), ensure_ascii=False
        )
        session.followup_queue_json = json.dumps(
            state.get("followup_queue", []), ensure_ascii=False
        )
        session.followup_streak = state.get("followup_streak", 0)
        if state.get("current_topic"):
            session.current_topic = state["current_topic"]
        if state.get("competency_status"):
            session.competency_status_json = json.dumps(
                state["competency_status"], ensure_ascii=False
            )
        if state.get("live_assessment"):
            session.live_assessment_json = json.dumps(
                state["live_assessment"], ensure_ascii=False
            )
        if state.get("topic_plan"):
            session.topic_plan_json = json.dumps(state["topic_plan"], ensure_ascii=False)
        session.question_index = state.get("question_index", session.question_index)
        session.encouraged_this_round = state.get(
            "encouraged_this_round", session.encouraged_this_round
        )
        session.pending_action = state.get("next_action", "stream_question")

    def _apply_feedback_loop(self, resume: Resume, report, session: InterviewSession) -> None:
        if resume.structured_json:
            try:
                data = json.loads(resume.structured_json)
                gaps = list(report.next_round_focus[:3])
                planned = json.loads(session.competencies_planned_json or "[]")
                covered = json.loads(session.competencies_covered_json or "[]")
                uncovered = [c for c in planned if c not in covered]
                gaps.extend(uncovered[:3])
                notes = data.get("interview_feedback", [])
                notes.extend(gaps)
                data["interview_feedback"] = notes[-8:]
                resume.structured_json = json.dumps(data, ensure_ascii=False)
            except Exception:
                pass

    def _load_a_layer_seeds(
        self, job_id: int, resume_id: int, job: Job
    ) -> tuple[list[str], list[str]]:
        competencies: list[str] = []
        followup_queue: list[str] = []

        screening = (
            self.db.query(ScreeningResult)
            .filter(
                ScreeningResult.job_id == job_id,
                ScreeningResult.resume_id == resume_id,
            )
            .first()
        )
        if screening:
            try:
                followups = FollowupPack.model_validate_json(
                    screening.followups_json or '{"items":[]}'
                ).items
                followup_queue = [f.question for f in followups[:5]]
            except Exception:
                pass
            if screening.questions_json:
                try:
                    questions = QuestionPack.model_validate_json(screening.questions_json).items
                    competencies = [q.competency for q in questions if q.competency][:12]
                except Exception:
                    pass

        if not competencies and job.structured_json:
            try:
                jd = JDStructured.model_validate_json(job.structured_json)
                competencies = jd.required_skills[:8]
            except Exception:
                pass

        return competencies, followup_queue

    def _load_question_queue(
        self,
        job_id: int,
        resume_id: int,
        job: Job,
        competencies: list[str],
        config: InterviewConfig,
    ) -> list[dict]:
        queue: list[dict] = []
        screening = (
            self.db.query(ScreeningResult)
            .filter(
                ScreeningResult.job_id == job_id,
                ScreeningResult.resume_id == resume_id,
            )
            .first()
        )
        if screening and screening.questions_json:
            try:
                pack = QuestionPack.model_validate_json(screening.questions_json)
                queue = [
                    {
                        "question": q.question,
                        "competency": q.competency or "general",
                        "rubric": q.rubric,
                    }
                    for q in pack.items[: config.standardized_question_limit]
                ]
            except Exception:
                pass
        if not queue and competencies:
            for comp in competencies[: config.standardized_question_limit]:
                queue.append(
                    {
                        "question": f"请结合你的经历，详细说明你在「{comp}」方面的能力与案例。",
                        "competency": comp,
                        "rubric": "",
                    }
                )
        if not queue and job.structured_json:
            try:
                jd = JDStructured.model_validate_json(job.structured_json)
                for skill in jd.required_skills[: config.standardized_question_limit]:
                    queue.append(
                        {
                            "question": f"请介绍你在 {skill} 方面的实践经验。",
                            "competency": skill,
                            "rubric": "",
                        }
                    )
            except Exception:
                pass
        return queue

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
        if resume.assessment_notes:
            a_layer_brief += (
                f"\n\nCandidate assessment notes (for hiring context):\n"
                f"{resume.assessment_notes[:1500]}"
            )
        live = None
        if session.live_assessment_json:
            try:
                live = json.loads(session.live_assessment_json)
            except Exception:
                pass
        topic_plan = None
        if session.topic_plan_json:
            try:
                topic_plan = json.loads(session.topic_plan_json)
            except Exception:
                pass
        last_eval = None
        if session.last_evaluation_json:
            try:
                last_eval = json.loads(session.last_evaluation_json)
            except Exception:
                pass

        return InterviewGraphState(
            job_text=job.raw_text,
            resume_text=resume.raw_text,
            structured=structured.model_dump(),
            persona=session.persona,
            persona_prompt=session.persona_prompt or "",
            interview_config=json.loads(session.interview_config_json or "{}")
            if session.interview_config_json
            else InterviewConfig(persona=session.persona).model_dump(),
            running_summary=session.running_summary or "",
            round_count=session.round_count,
            max_rounds=self.settings.max_interview_rounds,
            messages=messages,
            topics_covered=json.loads(session.topics_covered_json or "[]"),
            risk_notes=json.loads(session.risk_notes_json or "[]"),
            evaluations_log=json.loads(session.evaluations_log_json or "[]"),
            competencies_planned=json.loads(session.competencies_planned_json or "[]"),
            competencies_covered=json.loads(session.competencies_covered_json or "[]"),
            competency_status=json.loads(session.competency_status_json or "{}"),
            followup_queue=json.loads(session.followup_queue_json or "[]"),
            followup_streak=session.followup_streak or 0,
            current_topic=session.current_topic or "",
            phase=session.phase or "opening",
            live_assessment=live,
            topic_plan=topic_plan,
            last_evaluation=last_eval,
            a_layer_context=a_layer_brief,
            rubric_context=self._rubric_context(job),
            question_queue=json.loads(session.question_queue_json or "[]"),
            question_index=session.question_index or 0,
            encouraged_this_round=session.encouraged_this_round or False,
        )

    def _rubric_context(self, job: Job) -> str:
        if not job.rubric_json:
            return ""
        try:
            data = json.loads(job.rubric_json)
            return json.dumps(data, ensure_ascii=False)
        except Exception:
            return job.rubric_json[:3000]

    @staticmethod
    def _last_assistant_from_messages(messages: list[dict[str, str]]) -> str:
        for m in reversed(messages):
            if m["role"] == "assistant":
                return m["content"][:200]
        return ""

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

    def _build_candidate_experience_flywheel(self, job_id: int) -> str:
        sessions = (
            self.db.query(InterviewSession)
            .filter(
                InterviewSession.job_id == job_id,
                InterviewSession.status == "completed",
                InterviewSession.candidate_feedback_json.isnot(None),
            )
            .order_by(InterviewSession.updated_at.desc())
            .limit(5)
            .all()
        )
        feedbacks: list[dict] = []
        for s in sessions:
            fb = self.parse_candidate_feedback(s)
            if fb:
                feedbacks.append(fb)
        if not feedbacks:
            return ""

        ratings = [f["rating"] for f in feedbacks if f.get("rating") is not None]
        avg = sum(ratings) / len(ratings) if ratings else 0.0
        comments = [
            f.get("comment", "").strip() for f in feedbacks if f.get("comment", "").strip()
        ]
        lines = [
            "=== Prior candidate experience (flywheel) ===",
            f"Average experience rating (last {len(feedbacks)}): {avg:.1f}/5",
        ]
        if comments:
            quoted = "; ".join(f'"{c[:80]}"' for c in comments[:5])
            lines.append(f"Recent comments: {quoted}")
        if avg <= 3:
            lines.append(
                "Guidance: if rating <= 3, prefer clearer questions and slightly warmer transitions."
            )
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
