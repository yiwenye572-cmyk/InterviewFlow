from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import Job, Resume, ScreeningResult
from app.schemas.api import (
    JobListResponse,
    JobOverviewResponse,
    JobResponse,
    JobResumeListResponse,
    ResumeListItem,
)
from app.services.document_parser import parse_document
from app.services.history_service import HistoryService
from app.services.job_templates import list_templates
from app.services.resume_extractor import extract_jd_structured
from app.services.rubric_parser import parse_rubric_text, rubric_to_context
from app.schemas.resume_structured import ResumeStructured

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _guess_title(text: str, filename: str) -> str:
    for line in text.splitlines()[:10]:
        line = line.strip()
        if line and len(line) < 80:
            if any(k in line for k in ("工程师", "开发", "经理", "Engineer", "Developer")):
                return line
    base = filename.rsplit(".", 1)[0]
    return base or "Untitled Job"


@router.get("/templates")
def get_job_templates():
    return {"templates": [t.model_dump() for t in list_templates()]}


@router.get("", response_model=JobListResponse)
def list_jobs(db: Session = Depends(get_db)):
    service = HistoryService(db)
    return JobListResponse(jobs=service.list_jobs())


@router.get("/{job_id}/overview", response_model=JobOverviewResponse)
def get_job_overview(job_id: int, db: Session = Depends(get_db)):
    service = HistoryService(db)
    overview = service.get_job_overview(job_id)
    if not overview:
        raise HTTPException(status_code=404, detail="Job not found")
    return overview


@router.delete("/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    service = HistoryService(db)
    if not service.delete_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True, "job_id": job_id}


def _resume_display_name(resume: Resume) -> str:
    if resume.structured_json:
        try:
            return ResumeStructured.model_validate_json(resume.structured_json).name
        except Exception:
            pass
    return resume.filename.rsplit(".", 1)[0]


@router.get("/{job_id}/resumes", response_model=JobResumeListResponse)
def list_job_resumes(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    resumes = db.query(Resume).filter(Resume.job_id == job_id).order_by(Resume.id.desc()).all()
    items: list[ResumeListItem] = []
    for resume in resumes:
        screening = (
            db.query(ScreeningResult)
            .filter(
                ScreeningResult.job_id == job_id,
                ScreeningResult.resume_id == resume.id,
            )
            .first()
        )
        items.append(
            ResumeListItem(
                resume_id=resume.id,
                filename=resume.filename,
                candidate_name=_resume_display_name(resume),
                parse_status=resume.parse_status,
                screened=screening is not None,
                final_score=screening.final_score if screening else None,
            )
        )
    return JobResumeListResponse(job_id=job_id, resumes=items)


@router.post("/{job_id}/rubric")
async def upload_rubric(
    job_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    content = await file.read()
    parsed = parse_document(file.filename or "rubric.txt", content)
    rubric = parse_rubric_text(parsed.raw_text)
    job.rubric_json = rubric_to_context(rubric)
    db.commit()
    return {"job_id": job_id, "summary": rubric.summary, "criteria_count": len(rubric.criteria)}


@router.post("", response_model=JobResponse)
async def create_job(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    content = await file.read()
    parsed = parse_document(file.filename or "job.txt", content)
    job = Job(
        title=_guess_title(parsed.raw_text, parsed.filename),
        filename=parsed.filename,
        raw_text=parsed.raw_text,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        structured = extract_jd_structured(parsed.raw_text)
        job.structured_json = structured.model_dump_json(ensure_ascii=False)
        if structured.title:
            job.title = structured.title
        db.commit()
        db.refresh(job)
    except Exception:
        pass

    return JobResponse(id=job.id, title=job.title, filename=job.filename)
