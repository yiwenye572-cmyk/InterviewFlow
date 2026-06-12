"""Smart retry policy for structured LLM completions."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.config import Settings, get_settings
from app.services.llm.errors import (
    LLMAPIError,
    LLMError,
    LLMJSONError,
    LLMTimeoutError,
    LLMValidationError,
)
from app.services.llm.extract import extract_json


@dataclass
class RetryAction:
    retry: bool
    model: str | None = None
    temperature: float | None = None
    timeout: float | None = None
    sleep_seconds: float = 0.0
    append_message: dict[str, str] | None = None


def classify_error(exc: Exception) -> LLMError:
    if isinstance(exc, LLMError):
        return exc
    if isinstance(exc, ValidationError):
        return LLMValidationError(str(exc))
    if isinstance(exc, json.JSONDecodeError):
        return LLMJSONError(str(exc))
    if isinstance(exc, TimeoutError):
        return LLMTimeoutError(str(exc))

    msg = str(exc).lower()
    if "timeout" in msg or "timed out" in msg:
        return LLMTimeoutError(str(exc))

    if isinstance(exc, RuntimeError):
        if "api error" in msg or "stream error" in msg:
            status = None
            for code in (401, 403, 429, 500, 502, 503):
                if str(code) in str(exc):
                    status = code
                    break
            return LLMAPIError(str(exc), status_code=status)
        if "invalid json" in msg or "jsondecode" in msg:
            return LLMJSONError(str(exc))

    return LLMAPIError(str(exc))


def get_structured_retry_action(
    error: LLMError,
    attempt: int,
    max_retries: int,
    *,
    model: str,
    temperature: float,
    timeout: float,
    schema_name: str,
    settings: Settings | None = None,
) -> RetryAction:
    settings = settings or get_settings()
    if attempt >= max_retries:
        return RetryAction(retry=False)

    if isinstance(error, LLMAPIError) and not error.retryable:
        return RetryAction(retry=False)

    plus_model = settings.qwen_model

    if isinstance(error, LLMJSONError):
        if attempt == 0:
            return RetryAction(
                retry=True,
                temperature=0.1,
                append_message={
                    "role": "user",
                    "content": (
                        "Your previous response was invalid JSON. "
                        f"Error: {error}. Return ONLY valid JSON, no markdown fences."
                    ),
                },
            )
        return RetryAction(
            retry=True,
            temperature=0.05,
            append_message={
                "role": "user",
                "content": "Return ONLY a single valid JSON object matching the required schema.",
            },
        )

    if isinstance(error, LLMValidationError):
        if attempt == 0:
            return RetryAction(
                retry=True,
                temperature=0.1,
                append_message={
                    "role": "user",
                    "content": (
                        f"Validation failed for schema {schema_name}. Error: {error}. "
                        "Fix field types and required keys. Return ONLY valid JSON."
                    ),
                },
            )
        return RetryAction(
            retry=True,
            model=plus_model,
            temperature=0.1,
            append_message={
                "role": "user",
                "content": (
                    f"Return ONLY valid JSON strictly matching schema {schema_name}."
                ),
            },
        )

    if isinstance(error, LLMTimeoutError):
        if attempt == 0:
            return RetryAction(retry=True, timeout=timeout)
        return RetryAction(
            retry=True,
            model=plus_model,
            timeout=timeout + 30,
        )

    if isinstance(error, LLMAPIError):
        if attempt == 0:
            return RetryAction(retry=True, sleep_seconds=1.0)
        fast = settings.qwen_model_fast
        next_model = plus_model if model == fast else model
        return RetryAction(retry=True, model=next_model, sleep_seconds=1.5)

    return RetryAction(retry=False)


def run_structured_completion(
    client: Any,
    messages: list[dict[str, str]],
    schema_cls: type,
    *,
    model: str | None = None,
    retries: int | None = None,
    purpose: str = "unknown",
    timeout: float | None = None,
) -> Any:
    settings = get_settings()
    max_retries = settings.llm_structured_max_retries if retries is None else retries
    working = list(messages)
    current_model = model or settings.qwen_model_fast
    temperature = 0.2
    current_timeout = float(timeout or settings.llm_timeout_default)
    schema_name = getattr(schema_cls, "__name__", "Schema")
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            content = client.complete(
                working,
                model=current_model,
                temperature=temperature,
                json_mode=True,
                purpose=purpose,
                timeout=current_timeout,
                retry_attempt=attempt,
                kind="structured",
            )
            data = extract_json(content)
            return schema_cls.model_validate(data)
        except Exception as exc:
            last_error = exc
            classified = classify_error(exc)
            action = get_structured_retry_action(
                classified,
                attempt,
                max_retries,
                model=current_model,
                temperature=temperature,
                timeout=current_timeout,
                schema_name=schema_name,
                settings=settings,
            )
            if not action.retry:
                break
            if action.model:
                current_model = action.model
            if action.temperature is not None:
                temperature = action.temperature
            if action.timeout is not None:
                current_timeout = action.timeout
            if action.sleep_seconds:
                time.sleep(action.sleep_seconds)
            if action.append_message:
                working = working + [action.append_message]

    raise RuntimeError(f"Structured completion failed after retries: {last_error}")
