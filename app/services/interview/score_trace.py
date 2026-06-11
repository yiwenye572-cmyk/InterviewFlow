"""Build per-round score deltas and audit trail for live assessment."""

from __future__ import annotations

from app.schemas.resume_structured import AnswerEvaluation, LiveAssessment, ScoreReviewResult
from app.services.interview.live_assessment import _apply_rule_caps, _weighted_scores


def compute_live_scores(evaluations_log: list[dict]) -> tuple[int, int]:
    if not evaluations_log:
        return 60, 60
    job_avg, comm_avg = _weighted_scores(evaluations_log)
    job_fit, comm = _apply_rule_caps(evaluations_log, job_avg, comm_avg)
    return job_fit, comm


def build_score_adjustments(
    *,
    job_before: int,
    job_after: int,
    comm_before: int,
    comm_after: int,
    evaluation: AnswerEvaluation,
    review: ScoreReviewResult,
    draft_score: int,
) -> list[dict]:
    adjustments: list[dict] = []

    partial_delta = review.adjusted_partial_score - draft_score
    if partial_delta != 0:
        adjustments.append(
            {
                "dimension": "partial_score",
                "delta": partial_delta,
                "reason": review.calibration_notes or "Calibrator adjusted partial score",
                "evidence": (review.evidence_quotes[0] if review.evidence_quotes else ""),
            }
        )

    if review.calibration_notes:
        adjustments.append(
            {
                "dimension": "calibration",
                "delta": 0,
                "reason": review.calibration_notes,
                "evidence": "; ".join(review.evidence_quotes[:2]),
            }
        )

    if evaluation.communication_signal in ("vague", "evasive"):
        adjustments.append(
            {
                "dimension": "communication",
                "delta": comm_after - comm_before,
                "reason": f"Communication signal: {evaluation.communication_signal}",
                "evidence": (review.evidence_quotes[0] if review.evidence_quotes else ""),
            }
        )

    if evaluation.answer_quality == "weak":
        adjustments.append(
            {
                "dimension": "job_fit",
                "delta": job_after - job_before,
                "reason": evaluation.followup_reason or evaluation.notes or "Weak answer quality",
                "evidence": (review.evidence_quotes[0] if review.evidence_quotes else ""),
            }
        )

    if evaluation.evidence_density == "low":
        adjustments.append(
            {
                "dimension": "job_fit",
                "delta": 0,
                "reason": "Low evidence density — job fit capped by rule",
                "evidence": "",
            }
        )

    if evaluation.off_topic:
        adjustments.append(
            {
                "dimension": "job_fit",
                "delta": job_after - job_before,
                "reason": "Off-topic or adversarial input",
                "evidence": evaluation.notes or "",
            }
        )

    if not adjustments and (job_after != job_before or comm_after != comm_before):
        adjustments.append(
            {
                "dimension": "live_aggregate",
                "delta": job_after - job_before,
                "reason": "Weighted live score updated from recent rounds",
                "evidence": "",
            }
        )

    return adjustments


def attach_score_trace(
    eval_dict: dict,
    *,
    evaluations_log_before: list[dict],
    evaluation: AnswerEvaluation,
    review: ScoreReviewResult,
    draft_score: int,
) -> dict:
    job_before, comm_before = compute_live_scores(evaluations_log_before)
    log_with_current = evaluations_log_before + [eval_dict]
    job_after, comm_after = compute_live_scores(log_with_current)

    adjustments = build_score_adjustments(
        job_before=job_before,
        job_after=job_after,
        comm_before=comm_before,
        comm_after=comm_after,
        evaluation=evaluation,
        review=review,
        draft_score=draft_score,
    )

    if eval_dict.get("input_guard_blocked"):
        adjustments.insert(
            0,
            {
                "dimension": "security",
                "delta": 0,
                "reason": eval_dict.get("guard_reason") or "Security guard blocked adversarial input",
                "evidence": eval_dict.get("guard_threat_type", ""),
            },
        )

    prev_partial = evaluations_log_before[-1].get("partial_score") if evaluations_log_before else None
    partial_delta = (
        review.adjusted_partial_score - prev_partial if prev_partial is not None else None
    )

    eval_dict.update(
        {
            "live_job_fit_before": job_before,
            "live_job_fit_after": job_after,
            "live_comm_before": comm_before,
            "live_comm_after": comm_after,
            "job_fit_delta": job_after - job_before,
            "comm_delta": comm_after - comm_before,
            "partial_score_delta": partial_delta,
            "score_adjustments": adjustments,
        }
    )
    return eval_dict


def build_score_timeline(evaluations_log: list[dict]) -> list[dict]:
    timeline = []
    for e in evaluations_log:
        timeline.append(
            {
                "round": e.get("round"),
                "live_job_fit_before": e.get("live_job_fit_before"),
                "live_job_fit_after": e.get("live_job_fit_after"),
                "live_comm_before": e.get("live_comm_before"),
                "live_comm_after": e.get("live_comm_after"),
                "job_fit_delta": e.get("job_fit_delta", 0),
                "comm_delta": e.get("comm_delta", 0),
                "partial_score": e.get("partial_score"),
                "partial_score_delta": e.get("partial_score_delta"),
                "answer_quality": e.get("answer_quality"),
                "score_adjustments": e.get("score_adjustments", []),
                "evidence_quotes": e.get("evidence_quotes", []),
                "calibration_notes": e.get("calibration_notes", ""),
                "input_guard_blocked": e.get("input_guard_blocked", False),
                "guard_threat_type": e.get("guard_threat_type", ""),
            }
        )
    return timeline
