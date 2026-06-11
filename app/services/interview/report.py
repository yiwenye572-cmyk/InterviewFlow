import json
from pathlib import Path

from app.config import get_settings
from app.schemas.resume_structured import InterviewReport, ResumeStructured
from app.services.llm import chat_completion, structured_completion

PROMPT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "prompts"


def generate_interview_report(
    job_text: str,
    structured: dict,
    messages: list[dict[str, str]],
    risk_notes: list[str],
) -> InterviewReport:
    settings = get_settings()
    system = (PROMPT_DIR / "generate_report.txt").read_text(encoding="utf-8")
    transcript = _format_transcript(messages)
    messages_payload = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": (
                f"Job Description:\n{job_text[:6000]}\n\n"
                f"Resume:\n{json.dumps(structured, ensure_ascii=False)}\n\n"
                f"Internal risk notes:\n{json.dumps(risk_notes, ensure_ascii=False)}\n\n"
                f"Interview transcript:\n{transcript}"
            ),
        },
    ]
    draft = structured_completion(
        messages_payload, InterviewReport, model=settings.qwen_model, retries=2
    )
    return _reflect_report(job_text, transcript, draft)


def _reflect_report(
    job_text: str, transcript: str, draft: InterviewReport
) -> InterviewReport:
    settings = get_settings()
    system = (PROMPT_DIR / "report_reflection.txt").read_text(encoding="utf-8")
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": (
                f"Job Description:\n{job_text[:4000]}\n\n"
                f"Transcript:\n{transcript}\n\n"
                f"Draft report:\n{draft.model_dump_json(ensure_ascii=False)}"
            ),
        },
    ]
    try:
        return structured_completion(
            messages, InterviewReport, model=settings.qwen_model_fast, retries=1
        )
    except Exception:
        return draft


def _format_transcript(messages: list[dict[str, str]]) -> str:
    lines = []
    for m in messages:
        role = "Interviewer" if m["role"] == "assistant" else "Candidate"
        lines.append(f"{role}: {m['content']}")
    return "\n".join(lines)


def compress_conversation_summary(
    messages: list[dict[str, str]], existing_summary: str = ""
) -> str:
    settings = get_settings()
    recent = _format_transcript(messages[-8:])
    prompt = [
        {
            "role": "system",
            "content": "Summarize interview progress in 3-5 bullet points for interviewer context.",
        },
        {
            "role": "user",
            "content": (
                f"Previous summary:\n{existing_summary or 'None'}\n\n"
                f"Recent conversation:\n{recent}"
            ),
        },
    ]
    return chat_completion(prompt, model=settings.qwen_model_fast, temperature=0.2)
