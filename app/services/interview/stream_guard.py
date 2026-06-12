"""Post-generation validation for streamed interviewer messages."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from app.config import get_settings
from app.services.interview.input_guard import (
    _JAILBREAK_PATTERNS,
    _OFF_TOPIC_COMMAND_PATTERNS,
    _PROMPT_LEAK_PATTERNS,
    _match_any,
)

StreamKind = Literal["opening", "followup", "question"]

_AI_LEAK_PATTERNS = [
    r"我是\s*(一个\s*)?(AI|人工智能|语言模型|大语言模型|LLM|聊天机器人)",
    r"作为\s*(一个\s*)?(AI|人工智能|语言模型|大语言模型)",
    r"\bChatGPT\b",
    r"\bOpenAI\b",
    r"我无法(像人类|像真人)",
]

_QUESTION_INVITE_PATTERNS = [
    r"[？?]",
    r"请(先|简单|简要)?介绍",
    r"能否",
    r"可以谈谈",
    r"聊一聊",
    r"说一下",
    r"分享一下",
]

_TECH_LEAD_DRIFT = [
    r"亲爱的",
    r"抱抱",
    r"超级棒哦",
    r"～",
    r"么么",
]

_HR_HOSTILE = [
    r"不合格",
    r"淘汰",
    r"废话",
    r"滚",
    r"太差了",
]

_HARD_FAIL_FLAGS = frozenset(
    {
        "stream_guard_ai_leak",
        "stream_guard_system_leak",
        "stream_guard_off_topic",
        "stream_guard_empty",
        "stream_guard_too_short",
        "stream_guard_no_question",
    }
)


@dataclass
class StreamGuardResult:
    text: str
    passed: bool
    guard_flags: list[str] = field(default_factory=list)
    used_rewrite: bool = False
    used_template: bool = False


def _effective_chars(text: str) -> int:
    return len(re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE))


def _check_persona_drift(text: str, persona: str) -> bool:
    if persona == "tech_lead":
        return bool(_match_any(text, _TECH_LEAD_DRIFT))
    if persona == "hr_friendly":
        return bool(_match_any(text, _HR_HOSTILE))
    return False


def validate_stream_output(
    text: str,
    *,
    kind: StreamKind,
    persona: str,
    candidate_name: str = "",
    current_topic: str = "",
) -> StreamGuardResult:
    settings = get_settings()
    raw = (text or "").strip()
    if len(raw) > settings.stream_guard_max_chars:
        raw = raw[: settings.stream_guard_max_chars]

    flags: list[str] = []

    if _effective_chars(raw) < 4:
        flags.append("stream_guard_empty")
    elif len(raw) < settings.stream_guard_min_chars:
        flags.append("stream_guard_too_short")

    if _match_any(raw, _AI_LEAK_PATTERNS):
        flags.append("stream_guard_ai_leak")

    leak_hits = _match_any(raw, _JAILBREAK_PATTERNS + _PROMPT_LEAK_PATTERNS)
    if leak_hits:
        flags.append("stream_guard_system_leak")

    if _match_any(raw, _OFF_TOPIC_COMMAND_PATTERNS):
        flags.append("stream_guard_off_topic")

    if kind in ("opening", "question") and not _match_any(raw, _QUESTION_INVITE_PATTERNS):
        flags.append("stream_guard_no_question")

    if _check_persona_drift(raw, persona):
        flags.append("stream_guard_persona_drift")

    passed = not any(f in _HARD_FAIL_FLAGS for f in flags)
    return StreamGuardResult(text=raw, passed=passed, guard_flags=flags)


def _candidate_name_from_state(state: dict[str, Any]) -> str:
    structured = state.get("structured") or {}
    if isinstance(structured, dict):
        name = structured.get("name") or ""
        if name and name != "Unknown":
            return str(name)
    return "候选人"


def _topic_from_state(state: dict[str, Any]) -> str:
    topic_plan = state.get("topic_plan") or {}
    if isinstance(topic_plan, dict):
        topic = topic_plan.get("next_topic") or topic_plan.get("competency_target") or ""
        if topic:
            return str(topic)
    return str(state.get("current_topic") or "岗位相关能力")


def template_fallback(
    kind: StreamKind,
    persona: str,
    state: dict[str, Any],
) -> str:
    name = _candidate_name_from_state(state)
    topic = _topic_from_state(state)

    if kind == "opening":
        if persona == "hr_friendly":
            return (
                f"{name}你好，欢迎参加本次面试。我会轻松聊一聊你的经历，"
                "请先简单介绍一下自己。"
            )
        return (
            f"你好{name}，我是本场技术面试官。接下来我会围绕岗位与项目经验提问，"
            "请先做一个 2 分钟左右的自我介绍。"
        )

    if kind == "followup":
        return (
            "你刚才提到的这一点能否再具体一些？"
            "例如职责、技术选型或量化结果。"
        )

    return (
        f"请结合你简历中的相关经历，谈谈「{topic}」方面你的实践与思考。"
    )


def _default_rewrite(text: str, *, kind: StreamKind, persona: str, flags: list[str]) -> str:
    from app.services.llm import chat_completion

    settings = get_settings()
    style = "严厉的技术总监" if persona == "tech_lead" else "亲切的 HR"
    messages = [
        {
            "role": "system",
            "content": (
                "你是面试输出修复器。只输出修复后的面试官话术，不要 JSON，不要解释。"
                f"保持 persona={persona}（{style}）。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"输出类型: {kind}\n"
                f"检测到的问题: {', '.join(flags) or 'none'}\n"
                f"原始草稿:\n{text}\n\n"
                "请输出修复后的单条面试官消息（中文，3-5 句，含明确提问）。"
            ),
        },
    ]
    return chat_completion(
        messages,
        model=settings.qwen_model_fast,
        temperature=0.3,
        purpose="stream_guard_rewrite",
    ).strip()


def ensure_stream_output(
    text: str,
    *,
    kind: StreamKind,
    persona: str,
    state: dict[str, Any],
    rewrite_fn: Callable[..., str] | None = None,
) -> StreamGuardResult:
    settings = get_settings()
    candidate_name = _candidate_name_from_state(state)
    topic = _topic_from_state(state)

    result = validate_stream_output(
        text,
        kind=kind,
        persona=persona,
        candidate_name=candidate_name,
        current_topic=topic,
    )

    needs_polish = (
        not result.passed
        or "stream_guard_persona_drift" in result.guard_flags
    )
    if not needs_polish:
        return result

    if settings.stream_guard_llm_rewrite:
        rewriter = rewrite_fn or _default_rewrite
        try:
            rewritten = rewriter(
                result.text,
                kind=kind,
                persona=persona,
                flags=result.guard_flags,
            )
            retry = validate_stream_output(
                rewritten,
                kind=kind,
                persona=persona,
                candidate_name=candidate_name,
                current_topic=topic,
            )
            if retry.passed:
                retry.used_rewrite = True
                return retry
        except Exception:
            pass

    fallback = template_fallback(kind, persona, state)
    return StreamGuardResult(
        text=fallback,
        passed=True,
        guard_flags=result.guard_flags + ["stream_guard_template_fallback"],
        used_template=True,
    )
