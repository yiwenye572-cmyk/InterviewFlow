from pathlib import Path

from app.config import get_settings
from app.services.llm import chat_completion

PROMPT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "prompts"


def build_persona_prompt(job_text: str, persona: str) -> str:
    settings = get_settings()
    system = (PROMPT_DIR / "persona_init.txt").read_text(encoding="utf-8")
    style_label = "严厉的技术总监" if persona == "tech_lead" else "亲切的 HR"
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": (
                f"Persona style: {persona} ({style_label})\n\n"
                f"Job Description:\n{job_text[:8000]}"
            ),
        },
    ]
    return chat_completion(messages, model=settings.qwen_model_fast, temperature=0.4)
