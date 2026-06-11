import json

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.entities import Job, Resume, ScreeningResult
from app.services.embedding import semantic_similarity, upsert_job_embedding, upsert_resume_embedding
from app.services.resume_extractor import extract_resume_structured, score_resume_match


def screen_job(db: Session, job_id: int) -> list[ScreeningResult]:
    job = db.get(Job, job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    upsert_job_embedding(job.id, job.raw_text)
    settings = get_settings()
    results: list[ScreeningResult] = []

    resumes = db.query(Resume).filter(Resume.job_id == job_id).all()
    for resume in resumes:
        result = _screen_single_resume(db, job, resume, settings.match_threshold)
        results.append(result)

    db.commit()
    return results


def _screen_single_resume(
    db: Session, job: Job, resume: Resume, threshold: int
) -> ScreeningResult:
    structured = None
    try:
        structured = extract_resume_structured(resume.raw_text)
        resume.structured_json = structured.model_dump_json(ensure_ascii=False)
        resume.summary_text = structured.summary or _build_summary(structured)
        resume.parse_status = "success"
    except Exception:
        resume.parse_status = "failed"
        resume.structured_json = None
        resume.summary_text = resume.raw_text[:2000]

    db.flush()

    semantic_score = semantic_similarity(
        job.id, resume.id, resume.summary_text or resume.raw_text
    )
    if resume.parse_status == "success" and structured:
        upsert_resume_embedding(resume.id, resume.summary_text or resume.raw_text)
        try:
            llm_result = score_resume_match(job.raw_text, structured, resume.raw_text)
            llm_score = float(llm_result.score)
            reasons = llm_result.reasons
            gaps = llm_result.gaps
            recommend = llm_result.recommend_interview
        except Exception:
            llm_score = semantic_score
            reasons = ["LLM scoring unavailable; using semantic score only."]
            gaps = []
            recommend = semantic_score >= threshold
    else:
        llm_score = semantic_score * 0.8
        reasons = ["Resume parsing failed; score based mainly on text similarity."]
        gaps = ["Structured resume data unavailable."]
        recommend = False

    final_score = round(semantic_score * 0.4 + llm_score * 0.6, 1)
    recommend_interview = recommend and final_score >= threshold

    existing = (
        db.query(ScreeningResult)
        .filter(ScreeningResult.resume_id == resume.id)
        .first()
    )
    if existing:
        existing.semantic_score = semantic_score
        existing.llm_score = llm_score
        existing.final_score = final_score
        existing.reasons_json = json.dumps(reasons, ensure_ascii=False)
        existing.gaps_json = json.dumps(gaps, ensure_ascii=False)
        existing.recommend_interview = recommend_interview
        screening = existing
    else:
        screening = ScreeningResult(
            job_id=job.id,
            resume_id=resume.id,
            semantic_score=semantic_score,
            llm_score=llm_score,
            final_score=final_score,
            reasons_json=json.dumps(reasons, ensure_ascii=False),
            gaps_json=json.dumps(gaps, ensure_ascii=False),
            recommend_interview=recommend_interview,
        )
        db.add(screening)

    db.flush()
    return screening


def _build_summary(structured) -> str:
    skills = ", ".join(structured.skills[:15])
    highlights = "; ".join(structured.highlights[:5])
    return (
        f"{structured.name}, {structured.years_experience} years experience. "
        f"Skills: {skills}. Highlights: {highlights}"
    )
