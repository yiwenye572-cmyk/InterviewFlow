"""Background async interview report generation with stage progress."""

from __future__ import annotations

import json
import threading

from app.database import SessionLocal
from app.models.entities import InterviewSession, Job, Resume
from app.services.interview.report import (
    format_transcript,
    generate_report_draft,
    reflect_report,
)
from app.services.interview.service import InterviewService

_lock = threading.Lock()
_running: set[int] = set()
_errors: dict[int, str] = {}

STAGE_PROGRESS: dict[str, tuple[int, str]] = {
    "report_queued": (10, "排队中"),
    "report_draft": (45, "正在生成初稿"),
    "report_reflect": (80, "正在校准报告"),
    "completed": (100, "完成"),
    "report_failed": (0, "生成失败"),
}


def get_error(session_id: int) -> str | None:
    with _lock:
        return _errors.get(session_id)


def is_running(session_id: int) -> bool:
    with _lock:
        return session_id in _running


def status_from_session(session: InterviewSession) -> dict:
    if session.status == "completed" and session.report_json:
        progress, message = STAGE_PROGRESS["completed"]
        return {
            "session_id": session.id,
            "job_id": session.job_id,
            "status": "completed",
            "stage": "completed",
            "progress": progress,
            "message": message,
            "error": None,
        }

    stage = session.pending_action or "report_queued"
    if session.status == "failed" or stage == "report_failed":
        progress, message = STAGE_PROGRESS["report_failed"]
        return {
            "session_id": session.id,
            "job_id": session.job_id,
            "status": "failed",
            "stage": "report_failed",
            "progress": progress,
            "message": message,
            "error": get_error(session.id),
        }

    if session.status == "generating_report":
        progress, message = STAGE_PROGRESS.get(stage, (15, "正在生成报告"))
        return {
            "session_id": session.id,
            "job_id": session.job_id,
            "status": "generating_report",
            "stage": stage,
            "progress": progress,
            "message": message,
            "error": None,
        }

    progress, message = STAGE_PROGRESS.get(stage, (0, "等待生成"))
    return {
        "session_id": session.id,
        "job_id": session.job_id,
        "status": session.status,
        "stage": stage,
        "progress": progress,
        "message": message,
        "error": None,
    }


def start_report_generation(session_id: int) -> None:
    with _lock:
        if session_id in _running:
            return
        _running.add(session_id)
        _errors.pop(session_id, None)

    thread = threading.Thread(
        target=_run_report_worker, args=(session_id,), daemon=True
    )
    thread.start()


def _set_stage(db, session: InterviewSession, pending_action: str) -> None:
    session.pending_action = pending_action
    db.commit()


def _run_report_worker(session_id: int) -> None:
    db = SessionLocal()
    try:
        session = db.get(InterviewSession, session_id)
        if not session:
            return
        if session.status == "completed" and session.report_json:
            return

        job = db.get(Job, session.job_id)
        resume = db.get(Resume, session.resume_id)
        if not job or not resume:
            raise ValueError("Session data missing")

        service = InterviewService(db)
        messages = service._load_messages(session.id)
        structured = service._parse_structured(resume)
        risk_notes = json.loads(session.risk_notes_json or "[]")
        evaluations_log = json.loads(session.evaluations_log_json or "[]")
        live = None
        if session.live_assessment_json:
            try:
                live = json.loads(session.live_assessment_json)
            except Exception:
                pass
        rubric_context = service._rubric_context(job)
        transcript = format_transcript(messages)

        _set_stage(db, session, "report_draft")
        draft = generate_report_draft(
            job.raw_text,
            structured.model_dump(),
            messages,
            risk_notes,
            evaluations_log=evaluations_log,
            live_assessment=live,
            rubric_context=rubric_context,
        )

        _set_stage(db, session, "report_reflect")
        report = reflect_report(job.raw_text, transcript, draft)

        session = db.get(InterviewSession, session_id)
        if not session:
            return
        session.report_json = report.model_dump_json(ensure_ascii=False)
        session.status = "completed"
        session.pending_action = "completed"
        service._apply_feedback_loop(resume, report, session)
        db.commit()
    except Exception as exc:
        db.rollback()
        with _lock:
            _errors[session_id] = str(exc)[:300]
        try:
            session = db.get(InterviewSession, session_id)
            if session:
                session.status = "failed"
                session.pending_action = "report_failed"
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()
        with _lock:
            _running.discard(session_id)
