from pathlib import Path

from app.config import get_settings
from app.schemas.resume_structured import AnswerEvaluation, ScoreReviewResult
from app.services.llm import structured_completion

PROMPT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "prompts"


def review_score(
    *,
    question: str,
    answer: str,
    draft: AnswerEvaluation,
    job_excerpt: str,
    rubric_context: str = "",
) -> ScoreReviewResult:
    settings = get_settings()
    system = (PROMPT_DIR / "score_review.txt").read_text(encoding="utf-8")
    if rubric_context:
        system += f"\n\nCompany rubric:\n{rubric_context[:3000]}"
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": (
                f"Job excerpt:\n{job_excerpt[:2000]}\n\n"
                f"Question:\n{question}\n\n"
                f"Candidate answer:\n{answer}\n\n"
                f"Draft evaluation:\n{draft.model_dump_json(ensure_ascii=False)}"
            ),
        },
    ]
    try:
        return structured_completion(
            messages, ScoreReviewResult, model=settings.qwen_model_fast, retries=1
        )
    except Exception:
        score = draft.partial_score
        quality = draft.answer_quality
        comm = draft.communication_signal
        if draft.need_followup and quality == "adequate":
            quality = "weak"
            score = min(score, 45)
        if comm in ("vague", "evasive"):
            score = min(score, 40)
        return ScoreReviewResult(
            adjusted_partial_score=score,
            confidence=0.5,
            calibration_notes="Rule-based fallback calibration",
            adjusted_answer_quality=quality,
            adjusted_communication_signal=comm,
        )
