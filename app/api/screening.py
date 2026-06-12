import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import Job, Resume, ScreeningResult
from app.schemas.api import (
    QuestionPackResponse,
    ScreeningDetailResponse,
    ScreeningResultItem,
    ScreeningResultsResponse,
)
from app.schemas.resume_structured import (
    FollowupPack,
    JDStructured,
    QuestionPack,
    ResumeStructured,
)
from app.services.match_scorer import screen_job
from app.services.question_generator import generate_question_pack

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


def _load_structured_resume(resume: Resume) -> tuple[str, dict | None, list[str], str]:
    name = "Unknown"
    structured = None
    skills: list[str] = []
    summary = None
    if resume.structured_json:
        try:
            data = json.loads(resume.structured_json)
            structured = data
            name = data.get("name", "Unknown")
            skills = data.get("skills", [])
            summary = data.get("summary")
        except Exception:
            pass
    return name, structured, skills, summary or ""


def _screening_to_item(screening: ScreeningResult | None, resume: Resume) -> ScreeningResultItem:
    name, structured, skills, summary = _load_structured_resume(resume)
    if screening:
        followups = []
        try:
            pack = FollowupPack.model_validate_json(screening.followups_json or '{"items":[]}')
            followups = pack.items
        except Exception:
            pass
        dimension_scores = json.loads(screening.dimension_scores_json or "{}")
        score_flags = json.loads(screening.score_flags_json or "[]")
        return ScreeningResultItem(
            resume_id=resume.id,
            filename=resume.filename,
            candidate_name=name,
            parse_status=resume.parse_status,
            parse_quality=resume.parse_quality or "good",
            semantic_score=screening.semantic_score,
            llm_score=screening.llm_score,
            final_score=screening.final_score,
            reasons=json.loads(screening.reasons_json or "[]"),
            gaps=json.loads(screening.gaps_json or "[]"),
            recommend_interview=screening.recommend_interview,
            can_interview=True,
            decision_summary=screening.decision_summary,
            dimension_scores=dimension_scores,
            followups=followups,
            has_question_pack=bool(screening.questions_json),
            summary=summary or None,
            skills=skills,
            score_flags=score_flags,
        )
    return ScreeningResultItem(
        resume_id=resume.id,
        filename=resume.filename,
        candidate_name=name,
        parse_status=resume.parse_status,
        parse_quality=resume.parse_quality or "good",
        semantic_score=0,
        llm_score=0,
        final_score=0,
        reasons=["Not screened yet"],
        gaps=[],
        recommend_interview=False,
        can_interview=True,
        skills=skills,
        summary=summary or None,
    )


@router.get("/{job_id}/results", response_model=ScreeningResultsResponse)
def get_screening_results(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    resumes = db.query(Resume).filter(Resume.job_id == job_id).all()
    items: list[ScreeningResultItem] = []

    for resume in resumes:
        screening = (
            db.query(ScreeningResult)
            .filter(ScreeningResult.resume_id == resume.id)
            .first()
        )
        items.append(_screening_to_item(screening, resume))

    items.sort(key=lambda x: x.final_score, reverse=True)
    return ScreeningResultsResponse(job_id=job_id, results=items)


@router.get("/{job_id}/detail/{resume_id}", response_model=ScreeningDetailResponse)
def get_screening_detail(job_id: int, resume_id: int, db: Session = Depends(get_db)):
    resume = db.get(Resume, resume_id)
    if not resume or resume.job_id != job_id:
        raise HTTPException(status_code=404, detail="Resume not found")

    screening = (
        db.query(ScreeningResult)
        .filter(ScreeningResult.resume_id == resume_id)
        .first()
    )
    name, structured, _, _ = _load_structured_resume(resume)
    followups = []
    dimension_scores = {}
    decision_summary = None
    screening_dict = None
    if screening:
        try:
            followups = FollowupPack.model_validate_json(
                screening.followups_json or '{"items":[]}'
            ).items
        except Exception:
            pass
        dimension_scores = json.loads(screening.dimension_scores_json or "{}")
        decision_summary = screening.decision_summary
        screening_dict = {
            "semantic_score": screening.semantic_score,
            "llm_score": screening.llm_score,
            "final_score": screening.final_score,
            "reasons": json.loads(screening.reasons_json or "[]"),
            "gaps": json.loads(screening.gaps_json or "[]"),
            "recommend_interview": screening.recommend_interview,
            "score_flags": json.loads(screening.score_flags_json or "[]"),
        }

    return ScreeningDetailResponse(
        job_id=job_id,
        resume_id=resume_id,
        candidate_name=name,
        parse_status=resume.parse_status,
        parse_quality=resume.parse_quality or "good",
        structured=structured,
        screening=screening_dict,
        followups=followups,
        dimension_scores=dimension_scores,
        decision_summary=decision_summary,
    )


@router.get("/{job_id}/questions/{resume_id}", response_model=QuestionPackResponse)
def get_question_pack(job_id: int, resume_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    resume = db.get(Resume, resume_id)
    if not job or not resume or resume.job_id != job_id:
        raise HTTPException(status_code=404, detail="Not found")

    screening = (
        db.query(ScreeningResult)
        .filter(ScreeningResult.resume_id == resume_id)
        .first()
    )
    if not screening:
        raise HTTPException(status_code=404, detail="Run screening first")

    if screening.questions_json:
        pack = QuestionPack.model_validate_json(screening.questions_json)
        return QuestionPackResponse(
            job_id=job_id,
            resume_id=resume_id,
            questions=pack.items,
            cached=True,
        )

    if not resume.structured_json:
        raise HTTPException(status_code=422, detail="Resume not structured; cannot generate questions")

    resume_structured = ResumeStructured.model_validate_json(resume.structured_json)
    job_structured = None
    if job.structured_json:
        try:
            job_structured = JDStructured.model_validate_json(job.structured_json)
        except Exception:
            pass

    try:
        pack = generate_question_pack(job.raw_text, job_structured, resume_structured)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    screening.questions_json = pack.model_dump_json(ensure_ascii=False)
    db.commit()
    return QuestionPackResponse(
        job_id=job_id,
        resume_id=resume_id,
        questions=pack.items,
        cached=False,
    )
