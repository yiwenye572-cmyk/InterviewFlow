"""In-memory async screening batches with limited concurrency."""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from app.config import get_settings
from app.database import SessionLocal
from app.models.entities import Resume
from app.services.match_scorer import prepare_job_screening, screen_single_resume

_lock = threading.Lock()
_batches: dict[str, BatchProgress] = {}


@dataclass
class BatchItem:
    resume_id: int
    filename: str
    status: str = "pending"
    error: str | None = None


@dataclass
class BatchProgress:
    batch_id: str
    job_id: int
    items: list[BatchItem] = field(default_factory=list)
    status: str = "running"

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def completed(self) -> int:
        return sum(1 for i in self.items if i.status in ("done", "failed"))

    @property
    def failed(self) -> int:
        return sum(1 for i in self.items if i.status == "failed")


def get_batch(batch_id: str) -> BatchProgress | None:
    with _lock:
        return _batches.get(batch_id)


def start_batch(job_id: int, resume_ids: list[int]) -> str:
    if not resume_ids:
        raise ValueError("resume_ids required for batch screening")

    db = SessionLocal()
    try:
        prepare_job_screening(db, job_id)
        resumes = (
            db.query(Resume)
            .filter(Resume.job_id == job_id, Resume.id.in_(resume_ids))
            .all()
        )
        if len(resumes) != len(set(resume_ids)):
            raise ValueError("One or more resume_ids not found for this job")
        resume_map = {r.id: r for r in resumes}
        ordered = [resume_map[rid] for rid in resume_ids if rid in resume_map]
    finally:
        db.close()

    batch_id = str(uuid.uuid4())
    progress = BatchProgress(
        batch_id=batch_id,
        job_id=job_id,
        items=[
            BatchItem(resume_id=r.id, filename=r.filename) for r in ordered
        ],
    )
    with _lock:
        _batches[batch_id] = progress

    settings = get_settings()
    workers = min(settings.screen_concurrency, max(1, len(ordered)))
    executor = ThreadPoolExecutor(max_workers=workers)
    for item in progress.items:
        executor.submit(_run_one, batch_id, job_id, item.resume_id, settings.match_threshold)
    executor.shutdown(wait=False)
    return batch_id


def _run_one(batch_id: str, job_id: int, resume_id: int, threshold: int) -> None:
    _set_item_status(batch_id, resume_id, "running", None)
    db = SessionLocal()
    try:
        from app.models.entities import Job
        from app.services.match_scorer import _ensure_jd_structured

        job = db.get(Job, job_id)
        resume = db.get(Resume, resume_id)
        if not job or not resume:
            raise ValueError("Job or resume not found")
        job_structured = _ensure_jd_structured(db, job)
        screen_single_resume(db, job, job_structured, resume, threshold, [])
        db.commit()
        _set_item_status(batch_id, resume_id, "done", None)
    except Exception as exc:
        db.rollback()
        _set_item_status(batch_id, resume_id, "failed", str(exc)[:200])
    finally:
        db.close()
        _maybe_complete(batch_id)


def _set_item_status(
    batch_id: str, resume_id: int, status: str, error: str | None
) -> None:
    with _lock:
        batch = _batches.get(batch_id)
        if not batch:
            return
        for item in batch.items:
            if item.resume_id == resume_id:
                item.status = status
                item.error = error
                break


def _maybe_complete(batch_id: str) -> None:
    with _lock:
        batch = _batches.get(batch_id)
        if not batch:
            return
        if batch.completed >= batch.total:
            batch.status = "completed"
