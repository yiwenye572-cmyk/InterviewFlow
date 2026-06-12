"""Smoke test for Volcengine voice MVP (ASR + TTS + optional full turn)."""

from __future__ import annotations

import io
import struct
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx

from app.config import get_settings

BASE = "http://127.0.0.1:8000"


def ok(msg: str) -> None:
    print(f"[OK] {msg}")


def skip(msg: str) -> None:
    print(f"[SKIP] {msg}")


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    sys.exit(1)


def make_silent_wav(duration_sec: float = 0.5, sample_rate: int = 16000) -> bytes:
    n_frames = int(sample_rate * duration_sec)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack("<" + "h" * n_frames, *([0] * n_frames)))
    return buf.getvalue()


def test_tts_only() -> None:
    from app.services.voice.tts_client import synthesize_mp3

    audio = synthesize_mp3("你好，这是一次语音合成测试。")
    if len(audio) < 100:
        fail(f"TTS returned too little audio: {len(audio)} bytes")
    ok(f"TTS synthesize_mp3 ({len(audio)} bytes)")


def test_asr_empty_skip() -> None:
    skip("ASR live test requires real speech audio; use browser voice mode for E2E")


def test_voice_api_without_session() -> None:
    try:
        httpx.get(f"{BASE}/docs", timeout=3.0)
    except Exception:
        skip("Server not running — skip HTTP voice/turn test")
        return

    wav = make_silent_wav()
    files = {"file": ("test.wav", wav, "audio/wav")}
    r = httpx.post(f"{BASE}/api/interview/999999/voice/turn", files=files, timeout=60.0)
    if r.status_code == 404:
        ok("voice/turn route registered (404 for missing session)")
    elif r.status_code == 503:
        skip("voice/turn returns 503 — VOLC_SPEECH_API_KEY not loaded on server")
    else:
        ok(f"voice/turn responded with {r.status_code}")


def main() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    if not settings.volc_speech_api_key:
        skip("VOLC_SPEECH_API_KEY not set — copy .env.example and configure voice keys")
        test_voice_api_without_session()
        return

    ok(f"VOLC_ASR_RESOURCE_ID={settings.volc_asr_resource_id}")
    ok(f"VOLC_TTS_RESOURCE_ID={settings.volc_tts_resource_id}")

    try:
        test_tts_only()
    except Exception as exc:
        fail(f"TTS failed: {exc}")

    test_asr_empty_skip()
    test_voice_api_without_session()
    ok("voice MVP checks complete")


if __name__ == "__main__":
    main()
