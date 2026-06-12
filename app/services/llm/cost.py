"""Token usage parsing and cost estimation."""

from __future__ import annotations

from typing import Any

# Rough CNY per 1K tokens (input, output) for demo cost tracking.
_MODEL_RATES: dict[str, tuple[float, float]] = {
    "qwen-plus": (0.0008, 0.002),
    "qwen-turbo": (0.0003, 0.0006),
    "qwen-max": (0.002, 0.006),
}


def _estimate_tokens_from_text(text: str) -> int:
    return max(1, len(text) // 4)


def parse_usage(response: Any, *, input_text: str, output_text: str) -> dict[str, Any]:
    input_tokens = 0
    output_tokens = 0
    estimated = True

    usage = getattr(response, "usage", None)
    if usage is None and hasattr(response, "output"):
        usage = getattr(response.output, "usage", None)

    if isinstance(usage, dict):
        input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
        estimated = False
    elif usage is not None:
        input_tokens = int(getattr(usage, "input_tokens", 0) or getattr(usage, "prompt_tokens", 0) or 0)
        output_tokens = int(
            getattr(usage, "output_tokens", 0) or getattr(usage, "completion_tokens", 0) or 0
        )
        estimated = input_tokens == 0 and output_tokens == 0

    if estimated or (input_tokens == 0 and output_tokens == 0):
        input_tokens = _estimate_tokens_from_text(input_text)
        output_tokens = _estimate_tokens_from_text(output_text)
        estimated = True

    return {
        "input": input_tokens,
        "output": output_tokens,
        "estimated": estimated,
    }


def estimate_cost_cny(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = _MODEL_RATES.get(model)
    if not rates:
        for key, val in _MODEL_RATES.items():
            if key in model:
                rates = val
                break
    if not rates:
        rates = (0.001, 0.002)

    in_rate, out_rate = rates
    return round((input_tokens / 1000.0) * in_rate + (output_tokens / 1000.0) * out_rate, 6)
