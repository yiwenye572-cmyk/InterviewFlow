from datetime import datetime, timezone

from app.schemas.resume_structured import AnswerEvaluation, LiveAssessment


def _weighted_scores(evaluations: list[dict]) -> tuple[float, float]:
    """Last round weighted 50%, prior two 25% each."""
    if not evaluations:
        return 60.0, 60.0
    recent = evaluations[-3:]
    weights = [0.25, 0.25, 0.5][-len(recent) :]
    total_w = sum(weights)
    job_sum = 0.0
    comm_sum = 0.0
    comm_map = {"strong": 80, "adequate": 55, "weak": 30}
    for e, w in zip(recent, weights):
        job_sum += e.get("partial_score", 60) * w
        comm_sig = e.get("communication_signal", "clear")
        q = e.get("answer_quality", "adequate")
        base = comm_map.get(q, 55)
        if comm_sig == "vague":
            base = min(base, 40)
        elif comm_sig == "evasive":
            base = min(base, 30)
        comm_sum += base * w
    return job_sum / total_w, comm_sum / total_w


def _apply_rule_caps(evaluations: list[dict], job_fit: float, comm: float) -> tuple[int, int]:
    if not evaluations:
        return int(round(job_fit)), int(round(comm))
    last = evaluations[-1]
    if last.get("communication_signal") in ("vague", "evasive"):
        comm = min(comm, 40)
    if last.get("evidence_density") == "low":
        job_fit = min(job_fit, 50)
    if last.get("answer_quality") == "weak":
        job_fit = min(job_fit, 45)
        comm = min(comm, 35)
    return int(round(job_fit)), int(round(comm))


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

    job_avg, comm_avg = _weighted_scores(evaluations_log)
    job_fit, comm = _apply_rule_caps(evaluations_log, job_avg, comm_avg)

    strengths = list(existing.observed_strengths if existing else [])
    risks = list(existing.observed_risks if existing else [])
    for e in recent:
        if e.get("answer_quality") == "strong":
            note = e.get("competency_signal") or e.get("notes", "")
            if note and note not in strengths:
                strengths.append(note[:120])
        if (
            e.get("resume_mismatch")
            or e.get("off_topic")
            or e.get("answer_quality") == "weak"
            or e.get("communication_signal") in ("vague", "evasive")
        ):
            note = e.get("calibration_notes") or e.get("notes") or e.get("followup_reason", "")
            if note and note not in risks:
                risks.append(note[:120])
    for r in risk_notes[-3:]:
        if r not in risks:
            risks.append(r[:120])

    confidences = [e.get("confidence", 0.7) for e in recent if e.get("confidence") is not None]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.7
    cal_summary = recent[-1].get("calibration_notes", "") if recent else ""

    return LiveAssessment(
        round_count=round_count,
        current_phase=phase,
        provisional_job_fit=job_fit,
        provisional_communication=comm,
        observed_strengths=strengths[-5:],
        observed_risks=risks[-8:],
        last_updated=datetime.now(timezone.utc).isoformat(),
        score_confidence=round(avg_conf, 2),
        calibration_summary=cal_summary[:200],
    )


def evaluation_from_dict(data: dict) -> AnswerEvaluation:
    return AnswerEvaluation.model_validate(data)
