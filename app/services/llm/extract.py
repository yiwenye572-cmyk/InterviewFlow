"""Extract JSON objects from LLM text responses."""

from __future__ import annotations

import json
import re
from typing import Any

from app.services.llm.errors import LLMJSONError


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMJSONError(str(exc)) from exc
