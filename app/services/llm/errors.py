"""LLM harness error taxonomy."""

from __future__ import annotations


class LLMError(Exception):
    """Base error for harness-classified failures."""

    retryable: bool = True


class LLMTimeoutError(LLMError):
    """Request exceeded configured timeout."""

    retryable = True


class LLMAPIError(LLMError):
    """DashScope / HTTP API failure."""

    def __init__(self, message: str, *, status_code: int | None = None, code: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.code = code

    @property
    def retryable(self) -> bool:
        if self.status_code in (401, 403):
            return False
        if self.code and "invalid" in self.code.lower() and "key" in self.code.lower():
            return False
        return True


class LLMJSONError(LLMError):
    """Response was not valid JSON."""

    retryable = True


class LLMValidationError(LLMError):
    """JSON parsed but failed Pydantic schema validation."""

    retryable = True
