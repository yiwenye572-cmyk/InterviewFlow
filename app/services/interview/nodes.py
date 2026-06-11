import json
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.config import get_settings
from app.schemas.resume_structured import AnswerEvaluation, InterviewReport, ResumeStructured
from app.services.interview.persona import build_persona_prompt
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


def init_persona_node(state: InterviewGraphState) -> InterviewGraphState:
    persona_prompt = build_persona_prompt(state["job_text"], state["persona"])
    return {
        **state,
        "persona_prompt": persona_prompt,
        "next_action": "opening",
        "round_count": state.get("round_count", 0),
        "topics_covered": state.get("topics_covered", []),
        "risk_notes": state.get("risk_notes", []),
    }


def opening_node(state: InterviewGraphState) -> InterviewGraphState:
    structured = state.get("structured", {})
    name = structured.get("name", "候选人")
    reply = (
        f"你好 {name}，欢迎参加本次面试。我是今天的面试官，"
        f"接下来我会围绕岗位要求和你简历中的经历进行提问。"
        f"请先简单做个自我介绍，重点说明与本岗位最相关的经验。"
    )
    messages = list(state.get("messages", []))
    messages.append({"role": "assistant", "content": reply})
    return {
        **state,
        "assistant_reply": reply,
        "messages": messages,
        "next_action": "wait_answer",
        "round_count": state.get("round_count", 0),
    }


def evaluate_answer_node(state: InterviewGraphState) -> InterviewGraphState:
    settings = get_settings()
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
                f"Candidate answer:\n{state.get('last_user_message', '')}"
            ),
        },
    ]
    evaluation = structured_completion(
        messages, AnswerEvaluation, model=settings.qwen_model_fast, retries=1
    )
    risk_notes = list(state.get("risk_notes", []))
    if evaluation.resume_mismatch:
        risk_notes.append(f"Resume mismatch: {evaluation.notes}")
    if evaluation.off_topic:
        risk_notes.append(f"Off-topic answer: {evaluation.notes}")

    round_count = state.get("round_count", 0) + 1
    topics = list(state.get("topics_covered", []))
    if evaluation.topic_for_next and not evaluation.need_followup:
        topics.append(evaluation.topic_for_next)

    next_action = "ask_question"
    if round_count >= state.get("max_rounds", settings.max_interview_rounds):
        next_action = "closing"

    return {
        **state,
        "last_evaluation": evaluation.model_dump(),
        "round_count": round_count,
        "topics_covered": topics,
        "risk_notes": risk_notes,
        "next_action": next_action,
    }


def route_after_evaluate(state: InterviewGraphState) -> str:
    action = state.get("next_action", "ask_question")
    if action == "closing":
        return "closing"
    return "ask_question"


def ask_question_node(state: InterviewGraphState) -> InterviewGraphState:
    settings = get_settings()
    system = (PROMPT_DIR / "ask_question.txt").read_text(encoding="utf-8")
    eval_data = state.get("last_evaluation") or {}
    history = _format_history(state.get("messages", []))
    structured = state.get("structured", {})
    ambiguities = structured.get("ambiguities", [])

    user_content = (
        f"{state.get('persona_prompt', '')}\n\n"
        f"Job Description:\n{state['job_text'][:4000]}\n\n"
        f"Candidate resume summary:\n{json.dumps(structured, ensure_ascii=False)}\n\n"
        f"Resume ambiguities to probe:\n{json.dumps(ambiguities, ensure_ascii=False)}\n\n"
        f"Topics already covered:\n{json.dumps(state.get('topics_covered', []), ensure_ascii=False)}\n\n"
        f"Last evaluation:\n{json.dumps(eval_data, ensure_ascii=False)}\n\n"
        f"Conversation so far:\n{history}\n\n"
        f"Running summary:\n{state.get('running_summary', 'None')}\n\n"
        "Generate the next interviewer message."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]
    reply = chat_completion(messages, model=settings.qwen_model, temperature=0.5)
    conv = list(state.get("messages", []))
    conv.append({"role": "assistant", "content": reply})
    return {
        **state,
        "assistant_reply": reply,
        "messages": conv,
        "next_action": "wait_answer",
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
        "next_action": "generate_report",
    }


def _last_assistant_message(messages: list[dict[str, str]]) -> str:
    for msg in reversed(messages):
        if msg["role"] == "assistant":
            return msg["content"]
    return ""


def _format_history(messages: list[dict[str, str]], limit: int = 12) -> str:
    recent = messages[-limit:]
    lines = []
    for m in recent:
        role = "Interviewer" if m["role"] == "assistant" else "Candidate"
        lines.append(f"{role}: {m['content']}")
    return "\n".join(lines)


def build_interview_graph():
    graph = StateGraph(InterviewGraphState)
    graph.add_node("init_persona", init_persona_node)
    graph.add_node("opening", opening_node)
    graph.add_node("evaluate_answer", evaluate_answer_node)
    graph.add_node("ask_question", ask_question_node)
    graph.add_node("closing", closing_node)

    graph.set_entry_point("init_persona")
    graph.add_edge("init_persona", "opening")
    graph.add_edge("opening", END)
    graph.add_conditional_edges(
        "evaluate_answer",
        route_after_evaluate,
        {"ask_question": "ask_question", "closing": "closing"},
    )
    graph.add_edge("ask_question", END)
    graph.add_edge("closing", END)
    return graph.compile()


def stream_question(state: InterviewGraphState):
    settings = get_settings()
    system = (PROMPT_DIR / "ask_question.txt").read_text(encoding="utf-8")
    eval_data = state.get("last_evaluation") or {}
    history = _format_history(state.get("messages", []))
    structured = state.get("structured", {})
    ambiguities = structured.get("ambiguities", [])

    user_content = (
        f"{state.get('persona_prompt', '')}\n\n"
        f"Job Description:\n{state['job_text'][:4000]}\n\n"
        f"Candidate resume summary:\n{json.dumps(structured, ensure_ascii=False)}\n\n"
        f"Resume ambiguities to probe:\n{json.dumps(ambiguities, ensure_ascii=False)}\n\n"
        f"Topics already covered:\n{json.dumps(state.get('topics_covered', []), ensure_ascii=False)}\n\n"
        f"Last evaluation:\n{json.dumps(eval_data, ensure_ascii=False)}\n\n"
        f"Conversation so far:\n{history}\n\n"
        f"Running summary:\n{state.get('running_summary', 'None')}\n\n"
        "Generate the next interviewer message."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]
    return chat_completion_stream(messages, model=settings.qwen_model, temperature=0.5)


def stream_opening(state: InterviewGraphState):
    structured = state.get("structured", {})
    name = structured.get("name", "候选人")
    text = (
        f"你好 {name}，欢迎参加本次面试。我是今天的面试官，"
        f"接下来我会围绕岗位要求和你简历中的经历进行提问。"
        f"请先简单做个自我介绍，重点说明与本岗位最相关的经验。"
    )
    yield from _chunk_text(text)


def _chunk_text(text: str, size: int = 8):
    for i in range(0, len(text), size):
        yield text[i : i + size]
