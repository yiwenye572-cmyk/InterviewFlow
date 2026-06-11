from pathlib import Path

from app.config import get_settings
from app.schemas.resume_structured import InterviewConfig, JDStructured, PersonaProfile
from app.services.llm import structured_completion

PROMPT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "prompts"


def build_persona_profile(
    job_text: str,
    config: InterviewConfig,
    jd_structured: JDStructured | None = None,
) -> PersonaProfile:
    settings = get_settings()
    system = (PROMPT_DIR / "persona_init.txt").read_text(encoding="utf-8")
    style_label = "严厉的技术总监" if config.persona == "tech_lead" else "亲切的 HR"
    jd_part = ""
    if jd_structured:
        jd_part = f"\nStructured JD:\n{jd_structured.model_dump_json(ensure_ascii=False)}\n"
    role_part = f"\nCustom role title: {config.role_title}\n" if config.role_title else ""
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": (
                f"Persona style: {config.persona} ({style_label})\n"
                f"Strictness (1-5): {config.strictness}\n"
                f"Warmth (1-5): {config.warmth}\n"
                f"Interview difficulty: {config.difficulty}\n"
                f"Enable encouragement when candidate is stuck: {config.enable_encouragement}\n"
                f"{role_part}\n"
                f"Job Description:\n{job_text[:8000]}{jd_part}"
            ),
        },
    ]
    profile = structured_completion(
        messages, PersonaProfile, model=settings.qwen_model_fast, retries=2
    )
    if config.role_title:
        profile.role_title = config.role_title
    return profile
