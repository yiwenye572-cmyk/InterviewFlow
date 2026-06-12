"""Rule-based input guard for interview candidate messages."""

from __future__ import annotations

import re

from pydantic import BaseModel

_JAILBREAK_PATTERNS = [
    r"忽略(上文|之前|以上|所有)(的)?(指令|规则|提示|设定)",
    r"无视(指令|规则|提示|设定|上文)",
    r"forget\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"system\s*prompt",
    r"系统提示",
    r"你现在是(?!.*面试)",
    r"扮演(?!.*面试)",
    r"\bDAN\b",
    r"jailbreak",
    r"越狱",
    r"泄露.{0,6}(规则|提示|prompt|指令)",
    r"repeat.{0,10}(prompt|规则|指令)",
    r"输出.{0,6}(prompt|系统|规则)",
]

_PROMPT_LEAK_PATTERNS = [
    r"你的(指令|规则|prompt|系统提示)",
    r"what\s+are\s+your\s+instructions",
    r"show\s+me\s+your\s+prompt",
]

_OFF_TOPIC_COMMAND_PATTERNS = [
    r"帮我写(代码|程序|脚本)",
    r"写一首",
    r"翻译(以下|这段)",
]


class GuardResult(BaseModel):
    blocked: bool = False
    threat_type: str = "none"
    reason: str = ""
    hit_count: int = 0


def _match_any(text: str, patterns: list[str]) -> list[str]:
    hits = []
    lower = text.lower()
    for p in patterns:
        if re.search(p, text, re.IGNORECASE) or re.search(p, lower, re.IGNORECASE):
            hits.append(p)
    return hits


def check_input(content: str) -> GuardResult:
    text = (content or "").strip()
    if not text:
        return GuardResult()

    jailbreak_hits = _match_any(text, _JAILBREAK_PATTERNS)
    leak_hits = _match_any(text, _PROMPT_LEAK_PATTERNS)
    off_topic_hits = _match_any(text, _OFF_TOPIC_COMMAND_PATTERNS)

    if len(set(text)) <= 2 and len(text) > 20:
        return GuardResult(
            blocked=True,
            threat_type="jailbreak",
            reason="检测到异常重复输入",
            hit_count=1,
        )

    if jailbreak_hits:
        return GuardResult(
            blocked=True,
            threat_type="jailbreak",
            reason="检测到疑似越狱或指令覆盖",
            hit_count=len(jailbreak_hits),
        )

    if leak_hits:
        return GuardResult(
            blocked=True,
            threat_type="prompt_leak",
            reason="试图获取系统提示或内部规则",
            hit_count=len(leak_hits),
        )

    if off_topic_hits and len(off_topic_hits) >= 2:
        return GuardResult(
            blocked=True,
            threat_type="off_topic_command",
            reason="检测到离题指令请求",
            hit_count=len(off_topic_hits),
        )

    total = len(jailbreak_hits) + len(leak_hits) + len(off_topic_hits)
    if total >= 2:
        return GuardResult(
            blocked=True,
            threat_type="jailbreak",
            reason="检测到多项对抗性信号",
            hit_count=total,
        )

    return GuardResult()
