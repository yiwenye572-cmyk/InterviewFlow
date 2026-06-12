"""Unified DashScope LLM client with timeout, logging, and truncation."""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from http import HTTPStatus
from typing import Any, Generator

import dashscope
from dashscope import Generation

from app.config import get_settings
from app.services.llm.adapters import CallEndEvent, CallStartEvent, NoOpAdapter, TraceAdapter
from app.services.llm.cost import estimate_cost_cny, parse_usage
from app.services.llm.errors import LLMAPIError, LLMTimeoutError
from app.services.llm.log_store import append_call_log
from app.services.llm.truncate import truncate_messages

_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="llm-harness")


def ensure_api_key() -> None:
    settings = get_settings()
    dashscope.api_key = settings.dashscope_api_key


def _messages_input_text(messages: list[dict[str, str]]) -> str:
    return "\n".join(f"{m.get('role', '')}:{m.get('content', '')}" for m in messages)


def _call_generation(kwargs: dict[str, Any], timeout: float) -> Any:
    future = _executor.submit(Generation.call, **kwargs)
    try:
        return future.result(timeout=timeout)
    except FuturesTimeoutError as exc:
        future.cancel()
        raise LLMTimeoutError(f"LLM call exceeded {timeout}s timeout") from exc


def _raise_api_error(response: Any, *, stream: bool = False) -> None:
    prefix = "Qwen stream error" if stream else "Qwen API error"
    code = getattr(response, "code", "") or ""
    message = getattr(response, "message", response)
    status = getattr(response, "status_code", None)
    raise LLMAPIError(f"{prefix}: {code} - {message}", status_code=status, code=str(code))


class LLMClient:
    def __init__(self, adapter: TraceAdapter | None = None) -> None:
        self._adapter = adapter or NoOpAdapter()

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.3,
        json_mode: bool = False,
        purpose: str = "unknown",
        timeout: float | None = None,
        retry_attempt: int = 0,
        kind: str = "chat",
    ) -> str:
        ensure_api_key()
        settings = get_settings()
        resolved_model = model or settings.qwen_model
        resolved_timeout = float(timeout or settings.llm_timeout_default)

        truncated, trunc_flags = truncate_messages(
            messages,
            max_system_chars=settings.llm_max_system_chars,
            max_user_chars=settings.llm_max_user_chars,
        )
        call_id = uuid.uuid4().hex[:12]
        input_text = _messages_input_text(truncated)

        self._adapter.on_start(
            CallStartEvent(
                call_id=call_id,
                purpose=purpose,
                kind=kind,
                model=resolved_model,
                temperature=temperature,
            )
        )

        started = time.perf_counter()
        success = False
        error_type: str | None = None
        output_text = ""
        response = None

        try:
            kwargs: dict[str, Any] = {
                "model": resolved_model,
                "messages": truncated,
                "temperature": temperature,
                "result_format": "message",
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = _call_generation(kwargs, resolved_timeout)
            if response.status_code != HTTPStatus.OK:
                _raise_api_error(response)

            output_text = response.output.choices[0].message.content or ""
            success = True
            return output_text
        except LLMTimeoutError:
            error_type = "LLMTimeoutError"
            raise
        except LLMAPIError:
            error_type = "LLMAPIError"
            raise
        except Exception as exc:
            error_type = type(exc).__name__
            raise
        finally:
            latency_ms = int((time.perf_counter() - started) * 1000)
            tokens = parse_usage(
                response if success else None,
                input_text=input_text,
                output_text=output_text,
            ) if success else {
                "input": max(1, len(input_text) // 4),
                "output": 0,
                "estimated": True,
            }
            cost = estimate_cost_cny(resolved_model, tokens["input"], tokens["output"])

            record = {
                "call_id": call_id,
                "purpose": purpose,
                "kind": kind,
                "model": resolved_model,
                "temperature": temperature,
                "latency_ms": latency_ms,
                "success": success,
                "retry_attempt": retry_attempt,
                "truncated": trunc_flags,
                "tokens": tokens,
                "cost_cny": cost,
                "error_type": error_type,
            }
            append_call_log(record)
            self._adapter.on_end(
                CallEndEvent(
                    call_id=call_id,
                    purpose=purpose,
                    kind=kind,
                    model=resolved_model,
                    success=success,
                    latency_ms=latency_ms,
                    retry_attempt=retry_attempt,
                    extra=record,
                )
            )

    def stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.5,
        purpose: str = "unknown",
        timeout: float | None = None,
        retry_attempt: int = 0,
    ) -> Generator[str, None, None]:
        ensure_api_key()
        settings = get_settings()
        resolved_model = model or settings.qwen_model
        idle_timeout = float(timeout or settings.llm_timeout_stream)

        truncated, trunc_flags = truncate_messages(
            messages,
            max_system_chars=settings.llm_max_system_chars,
            max_user_chars=settings.llm_max_user_chars,
        )
        call_id = uuid.uuid4().hex[:12]
        input_text = _messages_input_text(truncated)

        self._adapter.on_start(
            CallStartEvent(
                call_id=call_id,
                purpose=purpose,
                kind="stream",
                model=resolved_model,
                temperature=temperature,
            )
        )

        started = time.perf_counter()
        success = False
        error_type: str | None = None
        chunks: list[str] = []

        try:
            responses = Generation.call(
                model=resolved_model,
                messages=truncated,
                temperature=temperature,
                result_format="message",
                stream=True,
                incremental_output=True,
            )
            last_chunk_at = time.perf_counter()
            for chunk in responses:
                if time.perf_counter() - last_chunk_at > idle_timeout:
                    raise LLMTimeoutError(
                        f"Stream idle exceeded {idle_timeout}s between chunks"
                    )
                if chunk.status_code != HTTPStatus.OK:
                    _raise_api_error(chunk, stream=True)
                content = chunk.output.choices[0].message.content
                if content:
                    chunks.append(content)
                    last_chunk_at = time.perf_counter()
                    yield content
            success = True
        except LLMTimeoutError:
            error_type = "LLMTimeoutError"
            raise
        except LLMAPIError:
            error_type = "LLMAPIError"
            raise
        except Exception as exc:
            error_type = type(exc).__name__
            raise
        finally:
            latency_ms = int((time.perf_counter() - started) * 1000)
            output_text = "".join(chunks)
            tokens = {
                "input": max(1, len(input_text) // 4),
                "output": max(0, len(output_text) // 4),
                "estimated": True,
            }
            cost = estimate_cost_cny(resolved_model, tokens["input"], tokens["output"])
            record = {
                "call_id": call_id,
                "purpose": purpose,
                "kind": "stream",
                "model": resolved_model,
                "temperature": temperature,
                "latency_ms": latency_ms,
                "success": success,
                "retry_attempt": retry_attempt,
                "truncated": trunc_flags,
                "tokens": tokens,
                "cost_cny": cost,
                "error_type": error_type,
            }
            append_call_log(record)
            self._adapter.on_end(
                CallEndEvent(
                    call_id=call_id,
                    purpose=purpose,
                    kind="stream",
                    model=resolved_model,
                    success=success,
                    latency_ms=latency_ms,
                    retry_attempt=retry_attempt,
                    extra=record,
                )
            )


_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
