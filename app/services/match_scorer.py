import json

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.entities import Job, Resume, ScreeningResult
from app.schemas.resume_structured import JDStructured, ResumeStructured
from app.services.embedding import semantic_similarity, upsert_job_embedding, upsert_resume_embedding
from app.services.followup_generator import generate_followup_pack
from app.services.resume_heuristics import (
    build_partial_structured,
    parse_failure_summary,
)
from app.services.resume_extractor import (
    extract_jd_structured,
    extract_resume_structured,
    score_resume_match,
)


def screen_job(db: Session, job_id: int) -> list[ScreeningResult]:
    job = db.get(Job, job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    job_structured = _ensure_jd_structured(db, job)
    score_flags: list[str] = []

    try:
        upsert_job_embedding(job.id, job.raw_text)
    except Exception:
        score_flags.append("embedding_job_fallback")

    settings = get_settings()
    results: list[ScreeningResult] = []

    resumes = db.query(Resume).filter(Resume.job_id == job_id).all()
    for resume in resumes:
        result = _screen_single_resume(
            db, job, job_structured, resume, settings.match_threshold, score_flags
        )
        results.append(result)

    db.commit()
    return results


def _ensure_jd_structured(db: Session, job: Job) -> JDStructured | None:
    if job.structured_json:
        try:
            return JDStructured.model_validate_json(job.structured_json)
        except Exception:
            pass
    try:
        structured = extract_jd_structured(job.raw_text)
        job.structured_json = structured.model_dump_json(ensure_ascii=False)
        if structured.title and job.title == "Untitled Job":
            job.title = structured.title
        db.flush()
        return structured
    except Exception:
        return None


def _screen_single_resume(
    db: Session,
    job: Job,
    job_structured: JDStructured | None,
    resume: Resume,
    threshold: int,
    global_flags: list[str],
) -> ScreeningResult:
    score_flags = list(global_flags)
    structured = None
    parse_exc: Exception | None = None
    text_len = len(resume.raw_text or "")

    if resume.parse_quality == "low" and text_len < 100:
        resume.parse_status = "failed"
        resume.structured_json = None
        resume.summary_text = resume.raw_text[:2000]
        score_flags.append("parse_too_short")
    elif resume.parse_quality == "scanned":
        resume.parse_status = "failed"
        resume.structured_json = None
        resume.summary_text = resume.raw_text[:2000]
        score_flags.append("parse_scanned")
    else:
        try:
            structured = extract_resume_structured(resume.raw_text)
            resume.structured_json = structured.model_dump_json(ensure_ascii=False)
            resume.summary_text = structured.summary or _build_summary(structured)
            resume.parse_status = "success" if resume.parse_quality == "good" else "partial"
        except Exception as exc:
            parse_exc = exc
            score_flags.append(f"llm_extract_failed:{str(exc)[:120]}")
            if text_len >= 100 and resume.parse_quality == "good":
                structured = build_partial_structured(resume.raw_text)
                resume.structured_json = structured.model_dump_json(ensure_ascii=False)
                resume.summary_text = structured.summary or resume.raw_text[:2000]
                resume.parse_status = "partial"
                score_flags.append("parse_partial_fallback")
            else:
                resume.parse_status = "failed"
                resume.structured_json = None
                resume.summary_text = resume.raw_text[:2000]

    db.flush()

    try:
        semantic_score = semantic_similarity(
            job.id, resume.id, resume.summary_text or resume.raw_text
        )
    except Exception:
        semantic_score = 50.0
        score_flags.append("embedding_fallback")

    dimension_scores: dict[str, int] = {}
    decision_summary = ""
    followups_json = "[]"
    gaps: list[str] = []
    reasons: list[str] = []

    if resume.parse_status in ("success", "partial") and structured:
        try:
            upsert_resume_embedding(resume.id, resume.summary_text or resume.raw_text)
        except Exception:
            score_flags.append("embedding_resume_fallback")
        try:
            llm_result = score_resume_match(
                job.raw_text, job_structured, structured, resume.raw_text
            )
            llm_score = float(llm_result.score)
            reasons = llm_result.reasons
            gaps = llm_result.gaps
            recommend = llm_result.recommend_interview
            dimension_scores = llm_result.dimension_scores or {}
            decision_summary = llm_result.decision_summary or ""
        except Exception:
            llm_score = semantic_score
            reasons = ["LLM scoring unavailable; using semantic score only."]
            gaps = []
            recommend = semantic_score >= threshold
            decision_summary = "自动降级：仅基于语义相似度评估。"
            score_flags.append("llm_score_fallback")
    else:
        llm_score = semantic_score * 0.8
        reasons = ["Resume parsing failed; score based mainly on text similarity."]
        gaps = ["Structured resume data unavailable."]
        recommend = False
        decision_summary = parse_failure_summary(
            parse_quality=resume.parse_quality or "good",
            text_len=text_len,
            exc=parse_exc,
        )
        score_flags.append("parse_failed")

    final_score = round(semantic_score * 0.4 + llm_score * 0.6, 1)
    recommend_interview = (
        recommend
        and final_score >= threshold
        and resume.parse_status in ("success", "partial")
    )

    if structured:
        try:
            followup_pack = generate_followup_pack(job_structured, structured, gaps)
            followups_json = followup_pack.model_dump_json(ensure_ascii=False)
        except Exception:
            followups_json = "[]"
            score_flags.append("followup_fallback")

    existing = (
        db.query(ScreeningResult)
        .filter(ScreeningResult.resume_id == resume.id)
        .first()
    )
    payload = dict(
        semantic_score=semantic_score,
        llm_score=llm_score,
        final_score=final_score,
        reasons_json=json.dumps(reasons, ensure_ascii=False),
        gaps_json=json.dumps(gaps, ensure_ascii=False),
        dimension_scores_json=json.dumps(dimension_scores, ensure_ascii=False),
        decision_summary=decision_summary,
        followups_json=followups_json,
        score_flags_json=json.dumps(list(set(score_flags)), ensure_ascii=False),
        recommend_interview=recommend_interview,
    )
    if existing:
        for key, value in payload.items():
            setattr(existing, key, value)
        screening = existing
    else:
        screening = ScreeningResult(
            job_id=job.id,
            resume_id=resume.id,
            **payload,
        )
        db.add(screening)

    db.flush()
    return screening


def _build_summary(structured: ResumeStructured) -> str:
    skills = ", ".join(structured.skills[:15])
    highlights = "; ".join(structured.highlights[:5])
    return (
        f"{structured.name}, {structured.years_experience} years experience. "
        f"Skills: {skills}. Highlights: {highlights}"
    )
