"""Volcengine TTS HTTP SSE client (openspeech unidirectional)."""

from __future__ import annotations

import base64
import json
import uuid
from typing import Any

import httpx

from app.config import get_settings

TTS_SSE_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse"


def _headers() -> dict[str, str]:
    settings = get_settings()
    if not settings.volc_speech_api_key:
        raise RuntimeError("VOLC_SPEECH_API_KEY is not configured")
    return {
        "X-Api-Key": settings.volc_speech_api_key,
        "X-Api-Resource-Id": settings.volc_tts_resource_id,
        "X-Api-Request-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def _append_audio(payload: dict[str, Any], parts: list[bytes]) -> None:
    code = payload.get("code")
    if code not in (0, None, 20000000):
        msg = payload.get("message") or payload
        raise RuntimeError(f"TTS error: {msg}")

    data = payload.get("data")
    if isinstance(data, str) and data:
        parts.append(base64.b64decode(data))
    elif isinstance(data, dict):
        chunk = data.get("audio") or data.get("data")
        if isinstance(chunk, str):
            parts.append(base64.b64decode(chunk))


def synthesize_mp3(text: str, speaker: str | None = None) -> bytes:
    settings = get_settings()
    cleaned = (text or "").strip()
    if not cleaned:
        return b""

    speaker_id = speaker or settings.volc_tts_speaker_hr
    body = {
        "user": {"uid": "ai-recruit-interview"},
        "req_params": {
            "text": cleaned[:2000],
            "speaker": speaker_id,
            "audio_params": {
                "format": "mp3",
                "sample_rate": 24000,
            },
        },
    }

    audio_parts: list[bytes] = []
    with httpx.Client(timeout=120.0) as client:
        with client.stream(
            "POST",
            TTS_SSE_URL,
            headers=_headers(),
            json=body,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    break
                try:
                    payload: dict[str, Any] = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                _append_audio(payload, audio_parts)

    return b"".join(audio_parts)
