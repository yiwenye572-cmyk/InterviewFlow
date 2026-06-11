import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import Job
from app.schemas.api import JobResponse
from app.services.document_parser import parse_document
from app.services.job_templates import list_templates
from app.services.rubric_parser import parse_rubric_text, rubric_to_context

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
    return JobResponse(id=job.id, title=job.title, filename=job.filename)
