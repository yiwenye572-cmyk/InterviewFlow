import json
import re
from typing import Any, Generator

import dashscope
from dashscope import Generation
from http import HTTPStatus

from app.config import get_settings


def _ensure_api_key() -> None:
    settings = get_settings()
    dashscope.api_key = settings.dashscope_api_key


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.3,
    json_mode: bool = False,
) -> str:
    _ensure_api_key()
    settings = get_settings()
    kwargs: dict[str, Any] = {
        "model": model or settings.qwen_model,
        "messages": messages,
        "temperature": temperature,
        "result_format": "message",
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = Generation.call(**kwargs)
    if response.status_code != HTTPStatus.OK:
        raise RuntimeError(
            f"Qwen API error: {response.code} - {getattr(response, 'message', response)}"
        )
    return response.output.choices[0].message.content


def chat_completion_stream(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.5,
) -> Generator[str, None, None]:
    _ensure_api_key()
    settings = get_settings()
    responses = Generation.call(
        model=model or settings.qwen_model,
        messages=messages,
        temperature=temperature,
        result_format="message",
        stream=True,
        incremental_output=True,
    )
    for chunk in responses:
        if chunk.status_code != HTTPStatus.OK:
            raise RuntimeError(
                f"Qwen stream error: {chunk.code} - {getattr(chunk, 'message', chunk)}"
            )
        content = chunk.output.choices[0].message.content
        if content:
            yield content


def structured_completion(
    messages: list[dict[str, str]],
    schema_cls: type,
    *,
    model: str | None = None,
    retries: int = 2,
) -> Any:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            content = chat_completion(
                messages,
                model=model,
                temperature=0.2 if attempt == 0 else 0.1,
                json_mode=True,
            )
            data = extract_json(content)
            return schema_cls.model_validate(data)
        except Exception as exc:
            last_error = exc
            messages = messages + [
                {
                    "role": "user",
                    "content": (
                        "Your previous response was invalid JSON or failed validation. "
                        f"Error: {exc}. Return ONLY valid JSON matching the schema."
                    ),
                }
            ]
    raise RuntimeError(f"Structured completion failed after retries: {last_error}")
