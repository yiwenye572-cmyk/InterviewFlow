import json
from pathlib import Path

from app.config import get_settings
from app.schemas.resume_structured import TopicPlan
from app.services.llm import structured_completion

PROMPT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "prompts"


def plan_next_topic(
    *,
    round_count: int,
    max_rounds: int,
    phase: str,
    competencies_planned: list[str],
    competencies_covered: list[str],
    followup_queue: list[str],
    topics_covered: list[str],
    last_evaluation: dict | None,
) -> TopicPlan:
    settings = get_settings()
    uncovered = [c for c in competencies_planned if c not in competencies_covered]

    if round_count >= max_rounds:
        return TopicPlan(phase="closing", should_close=True, rationale="Max rounds reached")

    coverage = (
        len(competencies_covered) / len(competencies_planned)
        if competencies_planned
        else 0.0
    )
    if coverage >= 0.8 and round_count >= 4:
        return TopicPlan(phase="closing", should_close=True, rationale="Sufficient competency coverage")

    if followup_queue and round_count <= 6:
        topic = followup_queue[0]
        return TopicPlan(
            phase="technical" if phase == "opening" else phase,
            next_topic=topic,
            competency_target=uncovered[0] if uncovered else "general",
            rationale="Priority A-layer followup topic",
        )

    system = (PROMPT_DIR / "topic_planner.txt").read_text(encoding="utf-8")
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "round_count": round_count,
                    "max_rounds": max_rounds,
                    "phase": phase,
                    "competencies_planned": competencies_planned,
                    "competencies_covered": competencies_covered,
                    "uncovered": uncovered,
                    "topics_covered": topics_covered,
                    "last_evaluation": last_evaluation or {},
                },
                ensure_ascii=False,
            ),
        },
    ]
    try:
        return structured_completion(
            messages, TopicPlan, model=settings.qwen_model_fast, retries=1
        )
    except Exception:
        target = uncovered[0] if uncovered else "project experience"
        return TopicPlan(
            phase="technical",
            next_topic=f"Please elaborate on {target}",
            competency_target=target,
            rationale="Fallback plan",
        )
