import asyncio
import json
from queue import Empty, Queue
from threading import Thread

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.schemas.api import (
    InterviewMessageRequest,
    InterviewStartRequest,
    InterviewStartResponse,
    ReportResponse,
)
from app.services.interview.service import InterviewService

router = APIRouter(prefix="/api/interview", tags=["interview"])


@router.post("/start", response_model=InterviewStartResponse)
def start_interview(payload: InterviewStartRequest, db: Session = Depends(get_db)):
    service = InterviewService(db)
    try:
        session = service.start_session(
            payload.job_id, payload.resume_id, payload.persona
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return InterviewStartResponse(
        session_id=session.id, persona=session.persona, status=session.status
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


@router.post("/{session_id}/message")
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
    return {
        "session_id": session.id,
        "round_count": session.round_count,
        "pending_action": session.pending_action,
    }


@router.post("/{session_id}/end")
def end_interview(session_id: int, db: Session = Depends(get_db)):
    service = InterviewService(db)
    try:
        session = service.end_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    report = json.loads(session.report_json) if session.report_json else None
    return ReportResponse(session_id=session.id, status=session.status, report=report)


@router.get("/report/{session_id}", response_model=ReportResponse)
def get_report(session_id: int, db: Session = Depends(get_db)):
    from app.models.entities import InterviewSession

    session = db.get(InterviewSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    report = json.loads(session.report_json) if session.report_json else None
    return ReportResponse(session_id=session.id, status=session.status, report=report)
