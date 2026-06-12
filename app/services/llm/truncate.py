"""Message truncation for LLM calls."""

from __future__ import annotations

_TRUNC_SUFFIX = "\n...[truncated]"


def truncate_messages(
    messages: list[dict[str, str]],
    *,
    max_system_chars: int,
    max_user_chars: int,
) -> tuple[list[dict[str, str]], dict[str, bool]]:
    flags = {"system": False, "user": False}
    result: list[dict[str, str]] = []

    for msg in messages:
        copied = dict(msg)
        role = copied.get("role", "")
        content = copied.get("content") or ""

        if role == "system" and len(content) > max_system_chars:
            copied["content"] = content[:max_system_chars] + _TRUNC_SUFFIX
            flags["system"] = True
        elif role == "user" and len(content) > max_user_chars:
            copied["content"] = content[:max_user_chars] + _TRUNC_SUFFIX
            flags["user"] = True

        result.append(copied)

    return result, flags
