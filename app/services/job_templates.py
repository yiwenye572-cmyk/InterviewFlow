import json
from pathlib import Path

from app.schemas.resume_structured import JobTemplate

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"


def list_templates() -> list[JobTemplate]:
    templates: list[JobTemplate] = []
    if not TEMPLATES_DIR.exists():
        return templates
    for path in sorted(TEMPLATES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            templates.append(JobTemplate.model_validate(data))
        except Exception:
            continue
    return templates


def load_template(template_id: str | None) -> JobTemplate | None:
    if not template_id:
        return None
    path = TEMPLATES_DIR / f"{template_id}.json"
    if not path.exists():
        return None
    try:
        return JobTemplate.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def infer_template_id(job_title: str, raw_text: str) -> str | None:
    text = (job_title + " " + raw_text[:500]).lower()
    if any(k in text for k in ("产品", "product", "pm")):
        return "product_manager"
    if any(k in text for k in ("工程师", "engineer", "开发", "backend", "后端", "java", "python")):
        return "tech_backend"
    return None
