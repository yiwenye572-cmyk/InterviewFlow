import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.entities import Job, Resume, ScreeningResult
from app.schemas.api import ScreeningResultItem, ScreeningResultsResponse
from app.services.match_scorer import screen_job

router = APIRouter(prefix="/api/screen", tags=["screening"])


@router.post("/{job_id}")
def run_screening(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        screen_job(db, job_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"job_id": job_id, "message": "Screening completed"}


@router.get("/{job_id}/results", response_model=ScreeningResultsResponse)
def get_screening_results(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    settings = get_settings()
    resumes = db.query(Resume).filter(Resume.job_id == job_id).all()
    items: list[ScreeningResultItem] = []

    for resume in resumes:
        screening = (
            db.query(ScreeningResult)
            .filter(ScreeningResult.resume_id == resume.id)
            .first()
        )
        name = "Unknown"
        if resume.structured_json:
            try:
                name = json.loads(resume.structured_json).get("name", "Unknown")
            except Exception:
                pass

        if screening:
            reasons = json.loads(screening.reasons_json or "[]")
            gaps = json.loads(screening.gaps_json or "[]")
            can_interview = (
                screening.recommend_interview
                and screening.final_score >= settings.match_threshold
            )
            items.append(
                ScreeningResultItem(
                    resume_id=resume.id,
                    filename=resume.filename,
                    candidate_name=name,
                    parse_status=resume.parse_status,
                    semantic_score=screening.semantic_score,
                    llm_score=screening.llm_score,
                    final_score=screening.final_score,
                    reasons=reasons,
                    gaps=gaps,
                    recommend_interview=screening.recommend_interview,
                    can_interview=can_interview,
                )
            )
        else:
            items.append(
                ScreeningResultItem(
                    resume_id=resume.id,
                    filename=resume.filename,
                    candidate_name=name,
                    parse_status=resume.parse_status,
                    semantic_score=0,
                    llm_score=0,
                    final_score=0,
                    reasons=["Not screened yet"],
                    gaps=[],
                    recommend_interview=False,
                    can_interview=False,
                )
            )

    items.sort(key=lambda x: x.final_score, reverse=True)
    return ScreeningResultsResponse(job_id=job_id, results=items)
