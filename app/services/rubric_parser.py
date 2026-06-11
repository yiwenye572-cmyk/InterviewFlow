import json
from pathlib import Path

from app.config import get_settings
from app.schemas.resume_structured import RubricProfile
from app.services.llm import structured_completion

PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


def parse_rubric_text(text: str) -> RubricProfile:
    settings = get_settings()
    messages = [
        {
            "role": "system",
            "content": (
                "Extract structured hiring rubric from company scoring guidelines. "
                "Return JSON: criteria (list of {name, levels: [{score, description}]}), summary."
            ),
        },
        {"role": "user", "content": text[:8000]},
    ]
    try:
        return structured_completion(
            messages, RubricProfile, model=settings.qwen_model_fast, retries=1
        )
    except Exception:
        return RubricProfile(summary=text[:500])


def rubric_to_context(rubric: RubricProfile) -> str:
    return json.dumps(rubric.model_dump(), ensure_ascii=False)
