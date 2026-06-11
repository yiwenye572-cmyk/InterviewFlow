import json
from pathlib import Path

from app.config import get_settings
from app.schemas.resume_structured import (
    FollowupPack,
    JDStructured,
    MatchLLMResult,
    QuestionPack,
    ResumeStructured,
)
from app.services.llm import structured_completion

PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def extract_jd_structured(raw_text: str) -> JDStructured:
    settings = get_settings()
    system = _load_prompt("jd_extract.txt")
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": f"Extract structured requirements from this job description:\n\n{raw_text[:10000]}",
        },
    ]
    return structured_completion(
        messages, JDStructured, model=settings.qwen_model_fast, retries=2
    )


def extract_resume_structured(raw_text: str) -> ResumeStructured:
    settings = get_settings()
    system = _load_prompt("resume_extract.txt")
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": f"Extract structured information from this resume:\n\n{raw_text[:12000]}",
        },
    ]
    return structured_completion(
        messages, ResumeStructured, model=settings.qwen_model_fast, retries=2
    )


def score_resume_match(
    job_text: str,
    job_structured: JDStructured | None,
    resume: ResumeStructured,
    raw_text: str,
) -> MatchLLMResult:
    settings = get_settings()
    system = _load_prompt("match_score.txt")
    jd_json = (
        job_structured.model_dump_json(ensure_ascii=False)
        if job_structured
        else json.dumps({"title": "Unknown"}, ensure_ascii=False)
    )
    resume_summary = resume.model_dump_json(ensure_ascii=False)
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": (
                f"Structured Job Description:\n{jd_json}\n\n"
                f"Job Description Raw Text:\n{job_text[:6000]}\n\n"
                f"Structured Resume:\n{resume_summary}\n\n"
                f"Resume Raw Text (reference):\n{raw_text[:6000]}"
            ),
        },
    ]
    return structured_completion(
        messages, MatchLLMResult, model=settings.qwen_model_fast, retries=2
    )
