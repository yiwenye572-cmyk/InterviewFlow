from datetime import datetime, timezone

from app.schemas.resume_structured import AnswerEvaluation, LiveAssessment


def update_live_assessment(
    *,
    round_count: int,
    phase: str,
    evaluations_log: list[dict],
    risk_notes: list[str],
    existing: LiveAssessment | None = None,
) -> LiveAssessment:
    recent = evaluations_log[-3:] if evaluations_log else []
    if not recent:
        return existing or LiveAssessment(
            round_count=round_count,
            current_phase=phase,
            last_updated=datetime.now(timezone.utc).isoformat(),
        )

    scores = [e.get("partial_score", 60) for e in recent]
    avg = sum(scores) / len(scores)
    comm_map = {"strong": 85, "adequate": 65, "weak": 45}
    comm_scores = [comm_map.get(e.get("answer_quality", "adequate"), 60) for e in recent]
    comm_avg = sum(comm_scores) / len(comm_scores)

    strengths = list(existing.observed_strengths if existing else [])
    risks = list(existing.observed_risks if existing else [])
    for e in recent:
        if e.get("answer_quality") == "strong":
            note = e.get("competency_signal") or e.get("notes", "")
            if note and note not in strengths:
                strengths.append(note[:120])
        if e.get("resume_mismatch") or e.get("off_topic") or e.get("answer_quality") == "weak":
            note = e.get("notes") or e.get("followup_reason", "")
            if note and note not in risks:
                risks.append(note[:120])
    for r in risk_notes[-3:]:
        if r not in risks:
            risks.append(r[:120])

    return LiveAssessment(
        round_count=round_count,
        current_phase=phase,
        provisional_job_fit=int(round(avg)),
        provisional_communication=int(round(comm_avg)),
        observed_strengths=strengths[-5:],
        observed_risks=risks[-8:],
        last_updated=datetime.now(timezone.utc).isoformat(),
    )


def evaluation_from_dict(data: dict) -> AnswerEvaluation:
    return AnswerEvaluation.model_validate(data)
