import json
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.config import get_settings
from app.schemas.resume_structured import AnswerEvaluation, LiveAssessment, TopicPlan
from app.services.interview.live_assessment import update_live_assessment
from app.services.interview.persona import build_persona_profile
from app.services.interview.planner import plan_next_topic
from app.services.llm import chat_completion, chat_completion_stream, structured_completion

PROMPT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "prompts"


class InterviewGraphState(TypedDict, total=False):
    job_text: str
    resume_text: str
    structured: dict
    persona: str
    persona_prompt: str
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
    phase: str
    competencies_planned: list[str]
    competencies_covered: list[str]
    followup_queue: list[str]
    evaluations_log: list[dict]
    live_assessment: dict
    topic_plan: dict


def init_persona_node(state: InterviewGraphState) -> InterviewGraphState:
    profile = build_persona_profile(
        state["job_text"], state["persona"]
    )
    return {
        **state,
        "persona_prompt": profile.system_prompt_block or profile.tone_description,
        "next_action": "stream_opening",
        "round_count": state.get("round_count", 0),
        "phase": state.get("phase", "opening"),
        "topics_covered": state.get("topics_covered", []),
        "risk_notes": state.get("risk_notes", []),
        "evaluations_log": state.get("evaluations_log", []),
        "competencies_planned": state.get("competencies_planned", []),
        "competencies_covered": state.get("competencies_covered", []),
        "followup_queue": state.get("followup_queue", []),
    }


def evaluate_answer_node(state: InterviewGraphState) -> InterviewGraphState:
    settings = get_settings()
    user_msg = (state.get("last_user_message") or "").strip()
    risk_notes = list(state.get("risk_notes", []))
    evaluations_log = list(state.get("evaluations_log", []))
    competencies_covered = list(state.get("competencies_covered", []))

    if len(user_msg) < 8:
        evaluation = AnswerEvaluation(
            need_followup=True,
            followup_reason="回答过短，请补充具体细节与实例",
            answer_quality="weak",
            notes="Answer too short",
            partial_score=35,
        )
    else:
        system = (PROMPT_DIR / "evaluate_answer.txt").read_text(encoding="utf-8")
        last_q = _last_assistant_message(state.get("messages", []))
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    f"Job Description excerpt:\n{state['job_text'][:3000]}\n\n"
                    f"Resume structured:\n{json.dumps(state.get('structured', {}), ensure_ascii=False)}\n\n"
                    f"Interview question:\n{last_q}\n\n"
                    f"Candidate answer:\n{user_msg}"
                ),
            },
        ]
        try:
            evaluation = structured_completion(
                messages, AnswerEvaluation, model=settings.qwen_model_fast, retries=1
            )
        except Exception:
            evaluation = AnswerEvaluation(
                need_followup=False,
                answer_quality="adequate",
                notes="Evaluation fallback",
                partial_score=60,
            )

    if evaluation.resume_mismatch:
        risk_notes.append(f"Resume mismatch: {evaluation.notes}")
    if evaluation.off_topic:
        risk_notes.append(f"Off-topic answer: {evaluation.notes}")
    if evaluation.answer_quality == "weak":
        risk_notes.append(f"Weak answer: {evaluation.notes or evaluation.followup_reason}")

    round_count = state.get("round_count", 0) + 1
    topics = list(state.get("topics_covered", []))
    if evaluation.topic_for_next and not evaluation.need_followup:
        topics.append(evaluation.topic_for_next)

    if evaluation.competency_signal and evaluation.answer_quality in ("strong", "adequate"):
        sig = evaluation.competency_signal.strip()
        if sig and sig not in competencies_covered:
            competencies_covered.append(sig)

    eval_dict = evaluation.model_dump()
    eval_dict["round"] = round_count
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
        "live_assessment": live.model_dump(),
    }


def route_decision_node(state: InterviewGraphState) -> InterviewGraphState:
    evaluation = state.get("last_evaluation") or {}
    round_count = state.get("round_count", 0)
    max_rounds = state.get("max_rounds", get_settings().max_interview_rounds)

    if round_count >= max_rounds:
        return {**state, "next_action": "stream_closing"}

    if evaluation.get("need_followup"):
        return {**state, "next_action": "stream_followup"}

    return {**state, "next_action": "plan_topic"}


def route_after_evaluate(state: InterviewGraphState) -> str:
    action = state.get("next_action", "plan_topic")
    if action == "stream_closing":
        return "closing"
    if action == "stream_followup":
        return "followup"
    return "plan"


def plan_topic_node(state: InterviewGraphState) -> InterviewGraphState:
    plan = plan_next_topic(
        round_count=state.get("round_count", 0),
        max_rounds=state.get("max_rounds", get_settings().max_interview_rounds),
        phase=state.get("phase", "opening"),
        competencies_planned=state.get("competencies_planned", []),
        competencies_covered=state.get("competencies_covered", []),
        followup_queue=state.get("followup_queue", []),
        topics_covered=state.get("topics_covered", []),
        last_evaluation=state.get("last_evaluation"),
    )

    followup_queue = list(state.get("followup_queue", []))
    if (
        followup_queue
        and plan.next_topic == followup_queue[0]
        and not plan.should_close
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
    }


def closing_node(state: InterviewGraphState) -> InterviewGraphState:
    reply = (
        "感谢你的回答，本次面试到此结束。"
        "我们会综合评估后尽快给你反馈。祝你一切顺利！"
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
    history = _format_history(
        state.get("messages", []), running_summary=state.get("running_summary", "")
    )
    structured = state.get("structured", {})
    ambiguities = structured.get("ambiguities", [])
    a_layer = state.get("a_layer_context", "")
    topic_plan = state.get("topic_plan") or {}

    mode_hint = {
        "opening": "Generate opening message asking for self-introduction.",
        "followup": (
            f"Generate follow-up on SAME topic. Reason: {eval_data.get('followup_reason', '')}"
        ),
        "new_topic": (
            f"Ask about new topic: {topic_plan.get('next_topic', '')}. "
            f"Target competency: {topic_plan.get('competency_target', '')}"
        ),
    }.get(question_mode, "")

    return (
        f"{state.get('persona_prompt', '')}\n\n"
        f"{a_layer}\n\n"
        f"Current phase: {state.get('phase', 'opening')}\n"
        f"Question mode: {question_mode}\n"
        f"{mode_hint}\n\n"
        f"Job Description:\n{state['job_text'][:4000]}\n\n"
        f"Candidate resume summary:\n{json.dumps(structured, ensure_ascii=False)}\n\n"
        f"Resume ambiguities to probe:\n{json.dumps(ambiguities, ensure_ascii=False)}\n\n"
        f"Competencies planned: {json.dumps(state.get('competencies_planned', []), ensure_ascii=False)}\n"
        f"Competencies covered: {json.dumps(state.get('competencies_covered', []), ensure_ascii=False)}\n\n"
        f"Topics already covered:\n{json.dumps(state.get('topics_covered', []), ensure_ascii=False)}\n\n"
        f"Last evaluation:\n{json.dumps(eval_data, ensure_ascii=False)}\n\n"
        f"Topic plan:\n{json.dumps(topic_plan, ensure_ascii=False)}\n\n"
        f"Conversation so far:\n{history}\n\n"
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
    user_content = _build_question_context(state, "opening")
    return _stream_from_prompt("opening_message.txt", user_content)


def stream_followup(state: InterviewGraphState):
    user_content = _build_question_context(state, "followup")
    return _stream_from_prompt("followup_question.txt", user_content)


def stream_question(state: InterviewGraphState):
    user_content = _build_question_context(state, "new_topic")
    return _stream_from_prompt("ask_question.txt", user_content)


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
    graph.add_node("route_decision", route_decision_node)
    graph.add_node("plan_topic", plan_topic_node)

    graph.set_entry_point("evaluate_answer")
    graph.add_edge("evaluate_answer", "route_decision")
    graph.add_conditional_edges(
        "route_decision",
        route_after_evaluate,
        {
            "followup": END,
            "plan": "plan_topic",
            "closing": END,
        },
    )
    graph.add_edge("plan_topic", END)
    return graph.compile()


def build_interview_graph():
    """Combined graph for documentation; runtime uses init + post_answer graphs."""
    return build_post_answer_graph()
