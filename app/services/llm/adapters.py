"""Trace adapter protocol (LangSmith / OTel reserved for future)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class CallStartEvent:
    call_id: str
    purpose: str
    kind: str
    model: str
    temperature: float


@dataclass
class CallEndEvent:
    call_id: str
    purpose: str
    kind: str
    model: str
    success: bool
    latency_ms: int
    retry_attempt: int
    extra: dict[str, Any]


class TraceAdapter(Protocol):
    def on_start(self, event: CallStartEvent) -> None: ...

    def on_end(self, event: CallEndEvent) -> None: ...


class NoOpAdapter:
    def on_start(self, event: CallStartEvent) -> None:
        return None

    def on_end(self, event: CallEndEvent) -> None:
        return None
