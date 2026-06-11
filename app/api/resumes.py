from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import Job, Resume
from app.schemas.api import ResumeUploadResponse
from app.services.document_parser import parse_document

router = APIRouter(prefix="/api/resumes", tags=["resumes"])


@router.get("/{resume_id}/structured")
def get_resume_structured(resume_id: int, db: Session = Depends(get_db)):
    import json

    resume = db.get(Resume, resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    structured = None
    if resume.structured_json:
        try:
            structured = json.loads(resume.structured_json)
        except Exception:
            structured = None
    return {
        "resume_id": resume_id,
        "parse_status": resume.parse_status,
        "parse_quality": resume.parse_quality,
        "structured": structured,
        "summary": resume.summary_text,
        "assessment_notes": resume.assessment_notes,
    }


@router.post("/{resume_id}/assessment-notes")
def set_assessment_notes(
    resume_id: int,
    notes: str = Form(...),
    db: Session = Depends(get_db),
):
    resume = db.get(Resume, resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    resume.assessment_notes = notes.strip()[:8000]
    db.commit()
    return {"resume_id": resume_id, "ok": True}


@router.post("", response_model=ResumeUploadResponse)
async def upload_resumes(
    job_id: int,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not files:
        raise HTTPException(status_code=422, detail="No resume files uploaded")

    uploaded: list[str] = []
    for file in files:
        content = await file.read()
        parsed = parse_document(file.filename or "resume.pdf", content)
        resume = Resume(
            job_id=job_id,
            filename=parsed.filename,
            raw_text=parsed.raw_text,
            parse_status="pending",
            parse_quality=parsed.parse_quality,
        )
        db.add(resume)
        uploaded.append(parsed.filename)

    db.commit()
    return ResumeUploadResponse(job_id=job_id, uploaded=uploaded, count=len(uploaded))
