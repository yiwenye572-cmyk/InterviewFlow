"""LLM harness package and backward-compatible public API."""

from __future__ import annotations

from typing import Any, Generator

from app.services.llm.client import LLMClient, ensure_api_key, get_llm_client
from app.services.llm.errors import LLMAPIError, LLMTimeoutError
from app.services.llm.extract import extract_json
from app.services.llm.retry import run_structured_completion

# Legacy import path for embedding.py
_ensure_api_key = ensure_api_key


def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.3,
    json_mode: bool = False,
    purpose: str = "unknown",
    timeout: float | None = None,
) -> str:
    client = get_llm_client()
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            return client.complete(
                messages,
                model=model,
                temperature=temperature,
                json_mode=json_mode,
                purpose=purpose,
                timeout=timeout,
                retry_attempt=attempt,
                kind="chat",
            )
        except (LLMAPIError, LLMTimeoutError) as exc:
            last_error = exc
            if attempt == 0 and exc.retryable:
                continue
            raise
    raise RuntimeError(f"Chat completion failed: {last_error}")


def chat_completion_stream(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.5,
    purpose: str = "unknown",
    timeout: float | None = None,
) -> Generator[str, None, None]:
    client = get_llm_client()
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            yield from client.stream(
                messages,
                model=model,
                temperature=temperature,
                purpose=purpose,
                timeout=timeout,
                retry_attempt=attempt,
            )
            return
        except (LLMAPIError, LLMTimeoutError) as exc:
            last_error = exc
            if attempt == 0 and exc.retryable:
                continue
            raise
    raise RuntimeError(f"Stream completion failed: {last_error}")


def structured_completion(
    messages: list[dict[str, str]],
    schema_cls: type,
    *,
    model: str | None = None,
    retries: int = 2,
    purpose: str = "unknown",
    timeout: float | None = None,
) -> Any:
    return run_structured_completion(
        get_llm_client(),
        messages,
        schema_cls,
        model=model,
        retries=retries,
        purpose=purpose,
        timeout=timeout,
    )


__all__ = [
    "LLMClient",
    "_ensure_api_key",
    "chat_completion",
    "chat_completion_stream",
    "ensure_api_key",
    "extract_json",
    "get_llm_client",
    "run_structured_completion",
    "structured_completion",
]
