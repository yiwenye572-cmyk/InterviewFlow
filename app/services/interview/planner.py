import json
from pathlib import Path

from app.config import get_settings
from app.schemas.resume_structured import TopicPlan
from app.services.llm import structured_completion

PROMPT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "prompts"

PHASE_BY_ROUND = [
    (2, "opening"),
    (5, "technical"),
    (8, "project"),
    (99, "behavioral"),
]


def infer_phase_from_round(round_count: int, current: str = "opening") -> str:
    if current == "closing":
        return "closing"
    for threshold, phase in PHASE_BY_ROUND:
        if round_count <= threshold:
            return phase if phase != "opening" or round_count <= 2 else "opening"
    return "behavioral"


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
    forced_new_topic: bool = False,
) -> TopicPlan:
    settings = get_settings()
    uncovered = [c for c in competencies_planned if c not in competencies_covered]
    suggested_phase = infer_phase_from_round(round_count, phase)

    if round_count >= max_rounds:
        return TopicPlan(phase="closing", should_close=True, rationale="Max rounds reached")

    coverage = (
        len(competencies_covered) / len(competencies_planned)
        if competencies_planned
        else 0.0
    )
    if coverage >= 0.8 and round_count >= 4:
        return TopicPlan(phase="closing", should_close=True, rationale="Sufficient competency coverage")

    if not forced_new_topic and followup_queue and round_count <= 6:
        topic = followup_queue[0]
        return TopicPlan(
            phase=suggested_phase if suggested_phase != "opening" else "technical",
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
                    "phase": suggested_phase,
                    "competencies_planned": competencies_planned,
                    "competencies_covered": competencies_covered,
                    "uncovered": uncovered,
                    "topics_covered": topics_covered,
                    "last_evaluation": last_evaluation or {},
                    "forced_new_topic": forced_new_topic,
                },
                ensure_ascii=False,
            ),
        },
    ]
    try:
        plan = structured_completion(
            messages, TopicPlan, model=settings.qwen_model_fast, retries=1
        )
        if plan.phase == "opening" and round_count > 2:
            plan.phase = suggested_phase
        return plan
    except Exception:
        target = uncovered[0] if uncovered else "project experience"
        return TopicPlan(
            phase=suggested_phase,
            next_topic=f"Please elaborate on {target}",
            competency_target=target,
            rationale="Fallback plan",
        )
