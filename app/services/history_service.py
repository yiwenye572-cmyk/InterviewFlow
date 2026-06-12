"""Job and interview history for persistence list UI."""

from __future__ import annotations

import json

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.entities import InterviewSession, Job, Resume, ScreeningResult
from app.schemas.api import InterviewSummaryItem, JobListItem, JobOverviewResponse
from app.schemas.resume_structured import JDStructured, ResumeStructured


def _format_dt(dt) -> str | None:
    if dt is None:
        return None
    return dt.isoformat() if hasattr(dt, "isoformat") else str(dt)


def _jd_summary(job: Job) -> tuple[str, dict | None]:
    if not job.structured_json:
        text = (job.raw_text or "")[:200].replace("\n", " ")
        return text or job.title, None
    try:
        jd = JDStructured.model_validate_json(job.structured_json)
        skills = ", ".join(jd.required_skills[:8]) if jd.required_skills else ""
        summary = jd.title or job.title
        if skills:
            summary += f" · 必备技能: {skills}"
        if jd.min_years:
            summary += f" · {jd.min_years}年+"
        return summary, jd.model_dump()
    except Exception:
        return job.title, None


def _candidate_name(resume: Resume, screening: ScreeningResult | None) -> str:
    if resume.structured_json:
        try:
            return ResumeStructured.model_validate_json(resume.structured_json).name
        except Exception:
            pass
    return resume.filename


def _report_fields(session: InterviewSession) -> dict:
    if not session.report_json:
        return {}
    try:
        report = json.loads(session.report_json)
    except Exception:
        return {}
    rationale = report.get("hiring_decision_rationale") or ""
    return {
        "job_fit_score": report.get("job_fit_score"),
        "communication_score": report.get("communication_score"),
        "overall_recommendation": report.get("overall_recommendation"),
        "report_summary": rationale[:120] + ("…" if len(rationale) > 120 else "") if rationale else None,
    }


class HistoryService:
    def __init__(self, db: Session):
        self.db = db

    def list_jobs(self) -> list[JobListItem]:
        jobs = self.db.query(Job).order_by(Job.created_at.desc()).all()
        items: list[JobListItem] = []
        for job in jobs:
            resume_count = (
                self.db.query(func.count(Resume.id)).filter(Resume.job_id == job.id).scalar() or 0
            )
            interview_count = (
                self.db.query(func.count(InterviewSession.id))
                .filter(InterviewSession.job_id == job.id)
                .scalar()
                or 0
            )
            completed = (
                self.db.query(func.count(InterviewSession.id))
                .filter(
                    InterviewSession.job_id == job.id,
                    InterviewSession.status == "completed",
                )
                .scalar()
                or 0
            )
            jd_summary, _ = _jd_summary(job)
            items.append(
                JobListItem(
                    id=job.id,
                    title=job.title,
                    filename=job.filename,
                    created_at=_format_dt(job.created_at),
                    resume_count=resume_count,
                    interview_count=interview_count,
                    completed_interview_count=completed,
                    jd_summary=jd_summary,
                    has_structured=bool(job.structured_json),
                )
            )
        return items

    def get_job_overview(self, job_id: int) -> JobOverviewResponse | None:
        job = self.db.get(Job, job_id)
        if not job:
            return None

        resume_count = (
            self.db.query(func.count(Resume.id)).filter(Resume.job_id == job.id).scalar() or 0
        )
        interview_count = (
            self.db.query(func.count(InterviewSession.id))
            .filter(InterviewSession.job_id == job.id)
            .scalar()
            or 0
        )
        completed = (
            self.db.query(func.count(InterviewSession.id))
            .filter(
                InterviewSession.job_id == job.id,
                InterviewSession.status == "completed",
            )
            .scalar()
            or 0
        )
        jd_summary, jd_structured = _jd_summary(job)

        sessions = (
            self.db.query(InterviewSession)
            .filter(InterviewSession.job_id == job_id)
            .order_by(InterviewSession.created_at.desc())
            .all()
        )

        interviews: list[InterviewSummaryItem] = []
        for s in sessions:
            resume = self.db.get(Resume, s.resume_id)
            screening = (
                self.db.query(ScreeningResult)
                .filter(
                    ScreeningResult.job_id == job_id,
                    ScreeningResult.resume_id == s.resume_id,
                )
                .first()
            )
            mode = "adaptive"
            if s.interview_config_json:
                try:
                    mode = json.loads(s.interview_config_json).get("interview_mode", "adaptive")
                except Exception:
                    pass
            report_fields = _report_fields(s)
            interviews.append(
                InterviewSummaryItem(
                    session_id=s.id,
                    resume_id=s.resume_id,
                    candidate_name=_candidate_name(resume, screening) if resume else "Unknown",
                    persona=s.persona,
                    interview_mode=mode,
                    status=s.status,
                    round_count=s.round_count,
                    created_at=_format_dt(s.created_at),
                    **report_fields,
                )
            )

        return JobOverviewResponse(
            job=JobListItem(
                id=job.id,
                title=job.title,
                filename=job.filename,
                created_at=_format_dt(job.created_at),
                resume_count=resume_count,
                interview_count=interview_count,
                completed_interview_count=completed,
                jd_summary=jd_summary,
                has_structured=bool(job.structured_json),
            ),
            jd_summary=jd_summary,
            jd_structured=jd_structured,
            interviews=interviews,
        )
