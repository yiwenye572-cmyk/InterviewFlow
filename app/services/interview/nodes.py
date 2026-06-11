import json
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.config import get_settings
from app.schemas.resume_structured import AnswerEvaluation, InterviewConfig, LiveAssessment
from app.services.interview.live_assessment import update_live_assessment
from app.services.interview.persona import build_persona_profile
from app.services.interview.planner import plan_next_topic
from app.services.interview.score_reviewer import review_score
from app.services.llm import chat_completion_stream, structured_completion

PROMPT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "prompts"


class InterviewGraphState(TypedDict, total=False):
    job_text: str
    resume_text: str
    structured: dict
    persona: str
    persona_prompt: str
    interview_config: dict
    running_summary: str
    round_count: int
    max_rounds: int
    messages: list[dict[str, str]]
    last_user_message: str
    last_evaluation: dict
    topics_covered: list[str]
    next_action: str
    assistant_reply: str
    report: dict
    risk_notes: list[str]
    a_layer_context: str
    rubric_context: str
    phase: str
    competencies_planned: list[str]
    competencies_covered: list[str]
    competency_status: dict[str, str]
    followup_queue: list[str]
    evaluations_log: list[dict]
    live_assessment: dict
    topic_plan: dict
    followup_streak: int
    current_topic: str
    force_new_topic: bool
    question_queue: list[dict]
    question_index: int
    encouraged_this_round: bool


def _get_config(state: InterviewGraphState) -> InterviewConfig:
    raw = state.get("interview_config") or {}
    return InterviewConfig.model_validate(raw)


def _max_followup(state: InterviewGraphState) -> int:
    return _get_config(state).max_followup_streak


def _init_competency_status(planned: list[str], existing: dict | None = None) -> dict[str, str]:
    status = dict(existing or {})
    for c in planned:
        if c and c not in status:
            status[c] = "uncovered"
    return status


def _update_competency_status(
    status: dict[str, str],
    evaluation: dict,
    *,
    target_competency: str = "",
    followup_streak: int = 0,
    forced_switch: bool = False,
    max_streak: int = 2,
) -> dict[str, str]:
    status = dict(status)
    comp = evaluation.get("competency_signal") or target_competency
    quality = evaluation.get("answer_quality", "adequate")
    comm = evaluation.get("communication_signal", "clear")

    if comp:
        if quality == "strong" or (quality == "adequate" and comm == "clear"):
            status[comp] = "covered"
        elif forced_switch or followup_streak >= max_streak or comm in ("vague", "evasive"):
            status[comp] = "at_risk"
        elif comp in status and status[comp] == "uncovered":
            status[comp] = "at_risk" if quality == "weak" else status[comp]

    if target_competency and target_competency in status:
        if forced_switch:
            status[target_competency] = "at_risk"
        elif quality in ("strong", "adequate") and comm == "clear":
            status[target_competency] = "covered"

    return status


def _infer_followup_type(streak: int) -> str:
    if streak <= 0:
        return "clarify"
    if streak == 1:
        return "quantify"
    return "deepen"


def init_persona_node(state: InterviewGraphState) -> InterviewGraphState:
    config = _get_config(state)
    profile = build_persona_profile(state["job_text"], config)
    planned = state.get("competencies_planned", [])
    return {
        **state,
        "persona": config.persona,
        "persona_prompt": profile.system_prompt_block or profile.tone_description,
        "next_action": "stream_opening",
        "round_count": state.get("round_count", 0),
        "phase": state.get("phase", "opening"),
        "topics_covered": state.get("topics_covered", []),
        "risk_notes": state.get("risk_notes", []),
        "evaluations_log": state.get("evaluations_log", []),
        "competencies_planned": planned,
        "competencies_covered": state.get("competencies_covered", []),
        "competency_status": _init_competency_status(
            planned, state.get("competency_status")
        ),
        "followup_queue": state.get("followup_queue", []),
        "followup_streak": state.get("followup_streak", 0),
        "current_topic": state.get("current_topic", ""),
        "question_queue": state.get("question_queue", []),
        "question_index": state.get("question_index", 0),
        "encouraged_this_round": False,
    }


def evaluate_answer_node(state: InterviewGraphState) -> InterviewGraphState:
    settings = get_settings()
    user_msg = (state.get("last_user_message") or "").strip()
    risk_notes = list(state.get("risk_notes", []))
    evaluations_log = list(state.get("evaluations_log", []))
    competencies_covered = list(state.get("competencies_covered", []))
    streak = state.get("followup_streak", 0)

    if len(user_msg) < 8:
        evaluation = AnswerEvaluation(
            need_followup=True,
            followup_reason="回答过短，请补充具体细节与实例",
            answer_quality="weak",
            notes="Answer too short",
            partial_score=35,
            communication_signal="vague",
            evidence_density="low",
            followup_type=_infer_followup_type(streak),
            candidate_state="stuck",
        )
    else:
        system = (PROMPT_DIR / "evaluate_answer.txt").read_text(encoding="utf-8")
        rubric = state.get("rubric_context", "")
        if rubric:
            system += f"\n\nCompany rubric:\n{rubric[:2000]}"
        last_q = _last_assistant_message(state.get("messages", []))
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    f"Job Description excerpt:\n{state['job_text'][:3000]}\n\n"
                    f"Resume structured:\n{json.dumps(state.get('structured', {}), ensure_ascii=False)}\n\n"
                    f"Interview question:\n{last_q}\n\n"
                    f"Candidate answer:\n{user_msg}\n\n"
                    f"Current followup_streak on topic: {streak}"
                ),
            },
        ]
        try:
            evaluation = structured_completion(
                messages, AnswerEvaluation, model=settings.qwen_model_fast, retries=1
            )
        except Exception:
            evaluation = AnswerEvaluation(
                need_followup=True,
                answer_quality="weak",
                notes="Evaluation fallback",
                partial_score=40,
                communication_signal="vague",
                evidence_density="low",
                followup_type=_infer_followup_type(streak),
                candidate_state="hesitant",
            )

    if evaluation.need_followup and evaluation.answer_quality == "adequate":
        evaluation.answer_quality = "weak"
        evaluation.partial_score = min(evaluation.partial_score, 45)
    if not evaluation.followup_type:
        evaluation.followup_type = _infer_followup_type(streak)

    return {
        **state,
        "last_evaluation": evaluation.model_dump(),
        "risk_notes": risk_notes,
        "evaluations_log": evaluations_log,
        "competencies_covered": competencies_covered,
        "encouraged_this_round": False,
    }


def score_review_node(state: InterviewGraphState) -> InterviewGraphState:
    evaluation = AnswerEvaluation.model_validate(state.get("last_evaluation", {}))
    user_msg = (state.get("last_user_message") or "").strip()
    last_q = _last_assistant_message(state.get("messages", []))
    risk_notes = list(state.get("risk_notes", []))
    evaluations_log = list(state.get("evaluations_log", []))
    competencies_covered = list(state.get("competencies_covered", []))
    competency_status = dict(state.get("competency_status", {}))
    followup_streak = state.get("followup_streak", 0)
    max_streak = _max_followup(state)

    review = review_score(
        question=last_q,
        answer=user_msg,
        draft=evaluation,
        job_excerpt=state["job_text"],
        rubric_context=state.get("rubric_context", ""),
    )

    evaluation.partial_score = review.adjusted_partial_score
    evaluation.answer_quality = review.adjusted_answer_quality
    evaluation.communication_signal = review.adjusted_communication_signal
    if review.adjusted_answer_quality == "weak":
        evaluation.need_followup = True

    if evaluation.resume_mismatch:
        risk_notes.append(f"Resume mismatch: {evaluation.notes}")
    if evaluation.off_topic:
        risk_notes.append(f"Off-topic answer: {evaluation.notes}")
    if evaluation.answer_quality == "weak":
        risk_notes.append(f"Weak answer: {evaluation.notes or evaluation.followup_reason}")
    if evaluation.communication_signal in ("vague", "evasive"):
        risk_notes.append(f"Poor communication: {review.calibration_notes or evaluation.notes}")

    round_count = state.get("round_count", 0) + 1
    topics = list(state.get("topics_covered", []))
    if evaluation.topic_for_next and not evaluation.need_followup:
        topics.append(evaluation.topic_for_next)

    target = state.get("current_topic", "") or (state.get("topic_plan") or {}).get(
        "competency_target", ""
    )
    competency_status = _update_competency_status(
        competency_status,
        evaluation.model_dump(),
        target_competency=target,
        followup_streak=followup_streak,
        max_streak=max_streak,
    )

    if evaluation.competency_signal and evaluation.answer_quality in ("strong", "adequate"):
        sig = evaluation.competency_signal.strip()
        if sig and sig not in competencies_covered and evaluation.communication_signal == "clear":
            competencies_covered.append(sig)

    eval_dict = evaluation.model_dump()
    eval_dict["round"] = round_count
    eval_dict["confidence"] = review.confidence
    eval_dict["calibration_notes"] = review.calibration_notes
    eval_dict["evidence_quotes"] = review.evidence_quotes
    evaluations_log.append(eval_dict)

    live = update_live_assessment(
        round_count=round_count,
        phase=state.get("phase", "opening"),
        evaluations_log=evaluations_log,
        risk_notes=risk_notes,
        existing=LiveAssessment.model_validate(state["live_assessment"])
        if state.get("live_assessment")
        else None,
    )

    return {
        **state,
        "last_evaluation": eval_dict,
        "round_count": round_count,
        "topics_covered": topics,
        "risk_notes": risk_notes,
        "evaluations_log": evaluations_log,
        "competencies_covered": competencies_covered,
        "competency_status": competency_status,
        "live_assessment": live.model_dump(),
    }


def route_decision_node(state: InterviewGraphState) -> InterviewGraphState:
    evaluation = state.get("last_evaluation") or {}
    config = _get_config(state)
    round_count = state.get("round_count", 0)
    max_rounds = state.get("max_rounds", get_settings().max_interview_rounds)
    streak = state.get("followup_streak", 0)
    max_streak = config.max_followup_streak
    need_followup = evaluation.get("need_followup", False)
    candidate_state = evaluation.get("candidate_state", "confident")

    if round_count >= max_rounds:
        return {**state, "next_action": "stream_closing", "followup_streak": 0}

    if (
        candidate_state in ("hesitant", "stuck")
        and config.enable_encouragement
        and not state.get("encouraged_this_round")
    ):
        return {
            **state,
            "next_action": "stream_encouragement",
            "encouraged_this_round": True,
        }

    if need_followup and max_streak > 0 and streak < max_streak:
        return {
            **state,
            "next_action": "stream_followup",
            "followup_streak": streak + 1,
            "force_new_topic": False,
        }

    competency_status = dict(state.get("competency_status", {}))
    target = state.get("current_topic", "") or (state.get("topic_plan") or {}).get(
        "competency_target", ""
    )
    if need_followup and streak >= max_streak and target:
        competency_status = _update_competency_status(
            competency_status,
            evaluation,
            target_competency=target,
            followup_streak=streak,
            forced_switch=True,
            max_streak=max_streak,
        )

    force = need_followup and streak >= max_streak
    return {
        **state,
        "next_action": "plan_topic",
        "followup_streak": 0,
        "force_new_topic": force,
        "competency_status": competency_status,
    }


def route_after_evaluate(state: InterviewGraphState) -> str:
    action = state.get("next_action", "plan_topic")
    if action == "stream_closing":
        return "closing"
    if action == "stream_encouragement":
        return "encourage"
    if action == "stream_followup":
        return "followup"
    return "plan"


def _plan_standardized_topic(state: InterviewGraphState):
    from app.schemas.resume_structured import TopicPlan

    config = _get_config(state)
    queue = state.get("question_queue", [])
    idx = state.get("question_index", 0)
    limit = config.standardized_question_limit

    if idx >= len(queue) or idx >= limit:
        return TopicPlan(phase="closing", should_close=True, rationale="Standardized queue complete")

    item = queue[idx]
    return TopicPlan(
        phase="technical",
        next_topic=item.get("question", ""),
        competency_target=item.get("competency", "general"),
        rationale=f"Standardized question {idx + 1}/{min(len(queue), limit)}",
    )


def plan_topic_node(state: InterviewGraphState) -> InterviewGraphState:
    config = _get_config(state)

    if config.interview_mode == "standardized":
        plan = _plan_standardized_topic(state)
    else:
        plan = plan_next_topic(
            round_count=state.get("round_count", 0),
            max_rounds=state.get("max_rounds", get_settings().max_interview_rounds),
            phase=state.get("phase", "opening"),
            competencies_planned=state.get("competencies_planned", []),
            competencies_covered=state.get("competencies_covered", []),
            followup_queue=state.get("followup_queue", []),
            topics_covered=state.get("topics_covered", []),
            last_evaluation=state.get("last_evaluation"),
            forced_new_topic=state.get("force_new_topic", False),
        )

    followup_queue = list(state.get("followup_queue", []))
    if (
        config.interview_mode == "adaptive"
        and followup_queue
        and plan.next_topic == followup_queue[0]
        and not plan.should_close
        and not state.get("force_new_topic")
    ):
        followup_queue.pop(0)

    next_action = "stream_closing" if plan.should_close else "stream_question"
    phase = plan.phase if not plan.should_close else "closing"

    return {
        **state,
        "phase": phase,
        "topic_plan": plan.model_dump(),
        "followup_queue": followup_queue,
        "next_action": next_action,
        "current_topic": plan.next_topic or plan.competency_target,
    }


def closing_node(state: InterviewGraphState) -> InterviewGraphState:
    reply = (
        "感谢您参加本次面试，面试环节到此结束。"
        "我们将综合评估结果，由招聘团队决定是否推进下一轮。"
    )
    conv = list(state.get("messages", []))
    conv.append({"role": "assistant", "content": reply})
    return {
        **state,
        "assistant_reply": reply,
        "messages": conv,
        "phase": "closing",
        "next_action": "generate_report",
    }


def _build_question_context(
    state: InterviewGraphState, question_mode: str = "new_topic"
) -> str:
    eval_data = state.get("last_evaluation") or {}
    config = _get_config(state)
    history = _format_history(
        state.get("messages", []), running_summary=state.get("running_summary", "")
    )
    structured = state.get("structured", {})
    ambiguities = structured.get("ambiguities", [])
    a_layer = state.get("a_layer_context", "")
    topic_plan = state.get("topic_plan") or {}
    quotes = eval_data.get("evidence_quotes") or []
    last_answer = (state.get("last_user_message") or "")[:500]

    mode_hint = {
        "opening": "Generate opening message asking for self-introduction.",
        "followup": (
            f"Follow-up type: {eval_data.get('followup_type', 'clarify')}. "
            f"Reason: {eval_data.get('followup_reason', '')}. "
            f"Quote candidate phrases: {quotes}. "
            f"Followup streak: {state.get('followup_streak', 0)}"
        ),
        "encouragement": (
            f"Candidate state: {eval_data.get('candidate_state', 'hesitant')}. "
            "Encourage only, no new question."
        ),
        "new_topic": (
            f"Ask about: {topic_plan.get('next_topic', '')}. "
            f"Competency: {topic_plan.get('competency_target', '')}"
        ),
    }.get(question_mode, "")

    return (
        f"{state.get('persona_prompt', '')}\n\n"
        f"{a_layer}\n\n"
        f"Interview mode: {config.interview_mode}\n"
        f"Difficulty: {config.difficulty}\n"
        f"Current phase: {state.get('phase', 'opening')}\n"
        f"Question mode: {question_mode}\n"
        f"{mode_hint}\n\n"
        f"Candidate last answer excerpt:\n{last_answer}\n\n"
        f"Job Description:\n{state['job_text'][:4000]}\n\n"
        f"Candidate resume summary:\n{json.dumps(structured, ensure_ascii=False)}\n\n"
        f"Resume ambiguities:\n{json.dumps(ambiguities, ensure_ascii=False)}\n\n"
        f"Competency status: {json.dumps(state.get('competency_status', {}), ensure_ascii=False)}\n\n"
        f"Last evaluation:\n{json.dumps(eval_data, ensure_ascii=False)}\n\n"
        f"Topic plan:\n{json.dumps(topic_plan, ensure_ascii=False)}\n\n"
        f"Conversation:\n{history}\n\n"
        f"Running summary:\n{state.get('running_summary', 'None')}\n\n"
        "Generate the next interviewer message."
    )


def _stream_from_prompt(system_file: str, user_content: str):
    settings = get_settings()
    system = (PROMPT_DIR / system_file).read_text(encoding="utf-8")
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]
    return chat_completion_stream(messages, model=settings.qwen_model, temperature=0.5)


def stream_opening(state: InterviewGraphState):
    return _stream_from_prompt("opening_message.txt", _build_question_context(state, "opening"))


def stream_followup(state: InterviewGraphState):
    return _stream_from_prompt("followup_question.txt", _build_question_context(state, "followup"))


def stream_question(state: InterviewGraphState):
    return _stream_from_prompt("ask_question.txt", _build_question_context(state, "new_topic"))


def stream_encouragement(state: InterviewGraphState):
    return _stream_from_prompt(
        "encouragement_message.txt", _build_question_context(state, "encouragement")
    )


def _last_assistant_message(messages: list[dict[str, str]]) -> str:
    for msg in reversed(messages):
        if msg["role"] == "assistant":
            return msg["content"]
    return ""


def _format_history(
    messages: list[dict[str, str]], limit: int = 12, running_summary: str = ""
) -> str:
    recent = messages[-limit:]
    lines = []
    for m in recent:
        role = "Interviewer" if m["role"] == "assistant" else "Candidate"
        lines.append(f"{role}: {m['content']}")
    text = "\n".join(lines)
    if len(text) > 6000 and running_summary:
        return running_summary + "\n\n" + "\n".join(lines[-6:])
    return text


def build_init_graph():
    graph = StateGraph(InterviewGraphState)
    graph.add_node("init_persona", init_persona_node)
    graph.set_entry_point("init_persona")
    graph.add_edge("init_persona", END)
    return graph.compile()


def build_post_answer_graph():
    graph = StateGraph(InterviewGraphState)
    graph.add_node("evaluate_answer", evaluate_answer_node)
    graph.add_node("score_review", score_review_node)
    graph.add_node("route_decision", route_decision_node)
    graph.add_node("plan_topic", plan_topic_node)

    graph.set_entry_point("evaluate_answer")
    graph.add_edge("evaluate_answer", "score_review")
    graph.add_edge("score_review", "route_decision")
    graph.add_conditional_edges(
        "route_decision",
        route_after_evaluate,
        {
            "encourage": END,
            "followup": END,
            "plan": "plan_topic",
            "closing": END,
        },
    )
    graph.add_edge("plan_topic", END)
    return graph.compile()


def build_interview_graph():
    return build_post_answer_graph()
