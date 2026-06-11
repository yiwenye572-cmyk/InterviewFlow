from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.schemas.resume_structured import JDStructured, PersonaProfile, TopicPlan
from app.services.llm import chat_completion, structured_completion

PROMPT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "prompts"


def build_persona_profile(
    job_text: str, persona: str, jd_structured: JDStructured | None = None
) -> PersonaProfile:
    settings = get_settings()
    system = (PROMPT_DIR / "persona_init.txt").read_text(encoding="utf-8")
    style_label = "严厉的技术总监" if persona == "tech_lead" else "亲切的 HR"
    jd_part = ""
    if jd_structured:
        jd_part = f"\nStructured JD:\n{jd_structured.model_dump_json(ensure_ascii=False)}\n"
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": (
                f"Persona style: {persona} ({style_label})\n\n"
                f"Job Description:\n{job_text[:8000]}{jd_part}"
            ),
        },
    ]
    return structured_completion(
        messages, PersonaProfile, model=settings.qwen_model_fast, retries=2
    )


def build_persona_prompt(job_text: str, persona: str) -> str:
    profile = build_persona_profile(job_text, persona)
    return profile.system_prompt_block or profile.tone_description
