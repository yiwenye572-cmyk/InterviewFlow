import asyncio
import json
from queue import Empty, Queue
from threading import Thread

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.schemas.api import (
    CandidateFeedbackRequest,
    CandidateFeedbackResponse,
    InterviewMessageRequest,
    InterviewMessageResponse,
    InterviewMessagesResponse,
    InterviewStartRequest,
    InterviewStartResponse,
    InterviewStatusResponse,
    ReportResponse,
)
from app.models.entities import InterviewSession
from app.services.interview.service import InterviewService
from app.services.interview.score_trace import build_score_timeline

router = APIRouter(prefix="/api/interview", tags=["interview"])


def _build_report_response(session: InterviewSession) -> ReportResponse:
    report = json.loads(session.report_json) if session.report_json else None
    evaluations_log = json.loads(session.evaluations_log_json or "[]")
    timeline = build_score_timeline(evaluations_log) if evaluations_log else None
    feedback = InterviewService.parse_candidate_feedback(session)
    return ReportResponse(
        session_id=session.id,
        status=session.status,
        report=report,
        evaluations_log=evaluations_log if report else None,
        score_timeline=timeline if report else None,
        candidate_feedback=feedback,
    )


@router.post("/start", response_model=InterviewStartResponse)
def start_interview(payload: InterviewStartRequest, db: Session = Depends(get_db)):
    service = InterviewService(db)
    try:
        session = service.start_session(
            payload.job_id, payload.resume_id, payload.persona, payload.config
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    mode = "adaptive"
    if session.interview_config_json:
        try:
            mode = json.loads(session.interview_config_json).get("interview_mode", "adaptive")
        except Exception:
            pass
    return InterviewStartResponse(
        session_id=session.id, persona=session.persona, status=session.status,
        interview_mode=mode,
    )


def _sse_event(data: str, event: str = "message") -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/{session_id}/stream")
async def stream_interview(session_id: int):
    queue: Queue[str | None] = Queue()
    error_holder: list[Exception] = []

    def producer():
        db = SessionLocal()
        try:
            service = InterviewService(db)
            for chunk in service.stream_pending(session_id):
                if chunk:
                    queue.put(chunk)
            queue.put(None)
        except Exception as exc:
            error_holder.append(exc)
            queue.put(None)
        finally:
            db.close()

    Thread(target=producer, daemon=True).start()

    async def event_generator():
        while True:
            try:
                chunk = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: queue.get(timeout=120)
                )
            except Empty:
                yield _sse_event("Stream timeout", event="error")
                break
            if chunk is None:
                break
            if error_holder:
                yield _sse_event(str(error_holder[0]), event="error")
                break
            yield _sse_event(chunk)
        yield _sse_event("[DONE]", event="done")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{session_id}/message", response_model=InterviewMessageResponse)
def send_message(
    session_id: int,
    payload: InterviewMessageRequest,
    db: Session = Depends(get_db),
):
    service = InterviewService(db)
    try:
        session = service.submit_answer(session_id, payload.content.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    live = None
    if session.live_assessment_json:
        try:
            live = json.loads(session.live_assessment_json)
        except Exception:
            pass

    return InterviewMessageResponse(
        session_id=session.id,
        round_count=session.round_count,
        phase=session.phase or "opening",
        pending_action=session.pending_action,
        live_assessment=live,
    )


@router.get("/{session_id}/live")
def get_live_assessment(session_id: int, db: Session = Depends(get_db)):
    service = InterviewService(db)
    live = service.get_live_assessment(session_id)
    if not live:
        raise HTTPException(status_code=404, detail="Live assessment not available yet")
    return live.model_dump()


@router.get("/{session_id}/status", response_model=InterviewStatusResponse)
def get_interview_status(session_id: int, db: Session = Depends(get_db)):
    service = InterviewService(db)
    try:
        status = service.get_status(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return InterviewStatusResponse(**status)


@router.get("/{session_id}/messages", response_model=InterviewMessagesResponse)
def get_interview_messages(session_id: int, db: Session = Depends(get_db)):
    service = InterviewService(db)
    try:
        messages = service.get_messages(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return InterviewMessagesResponse(session_id=session_id, messages=messages)


@router.post("/{session_id}/end")
def end_interview(session_id: int, db: Session = Depends(get_db)):
    service = InterviewService(db)
    try:
        session = service.end_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _build_report_response(session)


@router.post("/{session_id}/feedback", response_model=CandidateFeedbackResponse)
def submit_candidate_feedback(
    session_id: int,
    payload: CandidateFeedbackRequest,
    db: Session = Depends(get_db),
):
    service = InterviewService(db)
    try:
        feedback = service.submit_candidate_feedback(
            session_id, payload.rating, payload.comment or ""
        )
    except ValueError as exc:
        msg = str(exc)
        if "already submitted" in msg:
            raise HTTPException(status_code=409, detail=msg) from exc
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg) from exc
        raise HTTPException(status_code=400, detail=msg) from exc
    return CandidateFeedbackResponse(
        session_id=session_id, submitted=True, feedback=feedback
    )


@router.get("/report/{session_id}", response_model=ReportResponse)
def get_report(session_id: int, db: Session = Depends(get_db)):
    session = db.get(InterviewSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return _build_report_response(session)
