from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import Job, Resume
from app.schemas.api import ResumeUploadResponse
from app.services.document_parser import parse_document

router = APIRouter(prefix="/api/resumes", tags=["resumes"])


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
        )
        db.add(resume)
        uploaded.append(parsed.filename)

    db.commit()
    return ResumeUploadResponse(job_id=job_id, uploaded=uploaded, count=len(uploaded))
