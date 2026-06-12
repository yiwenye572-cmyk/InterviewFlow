"""Volcengine streaming ASR client (openspeech sauc, MVP: nostream whole utterance)."""

from __future__ import annotations

import asyncio
import io
import json
import uuid
import wave
from typing import Any

import websockets

from app.config import get_settings
from app.services.voice.volc_protocol import (
    COMPRESS_GZIP,
    FLAG_LAST_NO_SEQ,
    FLAG_POS_SEQ,
    MSG_AUDIO_ONLY,
    MSG_FULL_CLIENT,
    MSG_SERVER_ERROR,
    MSG_SERVER_FULL,
    SERIAL_JSON,
    SERIAL_NONE,
    decode_frames,
    encode_frame,
)

ASR_URL = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_nostream"


def _auth_headers() -> dict[str, str]:
    settings = get_settings()
    if not settings.volc_speech_api_key:
        raise RuntimeError("VOLC_SPEECH_API_KEY is not configured")
    return {
        "X-Api-Key": settings.volc_speech_api_key,
        "X-Api-Resource-Id": settings.volc_asr_resource_id,
        "X-Api-Request-Id": str(uuid.uuid4()),
        "X-Api-Connect-Id": str(uuid.uuid4()),
    }


def _client_config(audio_format: str = "pcm") -> dict[str, Any]:
    return {
        "user": {"uid": "ai-recruit-interview"},
        "audio": {
            "format": audio_format,
            "rate": 16000,
            "bits": 16,
            "channel": 1,
            "language": "zh-CN",
        },
        "request": {
            "model_name": "bigmodel",
            "enable_itn": True,
            "enable_punc": True,
            "enable_ddc": False,
        },
    }


def _prepare_audio(audio_bytes: bytes) -> tuple[bytes, str]:
    """Strip WAV container header; openspeech audio packets expect raw PCM."""
    if len(audio_bytes) >= 12 and audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            if wf.getsampwidth() != 2:
                raise ValueError(f"Unsupported sample width: {wf.getsampwidth()}")
            if wf.getnchannels() != 1:
                raise ValueError(f"Expected mono audio, got {wf.getnchannels()} channels")
            if wf.getframerate() != 16000:
                raise ValueError(f"Expected 16 kHz audio, got {wf.getframerate()} Hz")
            return wf.readframes(wf.getnframes()), "pcm"
    return audio_bytes, "pcm"


def _extract_text(frame: dict[str, Any]) -> str:
    data = frame.get("json") or {}
    result = data.get("result")
    if isinstance(result, dict) and result.get("text"):
        return str(result["text"]).strip()
    if isinstance(result, list):
        parts = [str(item.get("text", "")).strip() for item in result if item.get("text")]
        return " ".join(p for p in parts if p).strip()
    return str(data.get("text") or "").strip()


async def transcribe_wav_async(audio_bytes: bytes) -> str:
    if not audio_bytes:
        raise ValueError("Empty audio")

    pcm_bytes, audio_format = _prepare_audio(audio_bytes)
    if not pcm_bytes:
        raise ValueError("Empty PCM payload")

    headers = _auth_headers()
    config_payload = json.dumps(_client_config(audio_format), ensure_ascii=False).encode("utf-8")

    async with websockets.connect(
        ASR_URL,
        additional_headers=headers,
        max_size=16 * 1024 * 1024,
        open_timeout=30,
    ) as ws:
        await ws.send(
            encode_frame(
                MSG_FULL_CLIENT,
                config_payload,
                serialization=SERIAL_JSON,
                compression=COMPRESS_GZIP,
            )
        )

        chunk_size = 32000
        chunks = [pcm_bytes[i : i + chunk_size] for i in range(0, len(pcm_bytes), chunk_size)]
        if not chunks:
            raise ValueError("No audio chunks to send")

        for idx, chunk in enumerate(chunks):
            is_last = idx == len(chunks) - 1
            if is_last:
                flags = FLAG_LAST_NO_SEQ
                sequence = None
            else:
                flags = FLAG_POS_SEQ
                sequence = idx + 1
            await ws.send(
                encode_frame(
                    MSG_AUDIO_ONLY,
                    chunk,
                    flags=flags,
                    serialization=SERIAL_NONE,
                    compression=COMPRESS_GZIP,
                    sequence=sequence,
                )
            )

        final_text = ""
        buffer = b""
        while True:
            try:
                message = await asyncio.wait_for(ws.recv(), timeout=2.0)
            except asyncio.TimeoutError:
                if final_text:
                    break
                continue
            except websockets.exceptions.ConnectionClosed:
                break
            if isinstance(message, str):
                continue
            buffer += message
            frames, buffer = decode_frames(buffer)
            for frame in frames:
                if frame.get("msg_type") == MSG_SERVER_ERROR:
                    err = frame.get("error") or frame.get("error_raw")
                    raise RuntimeError(f"ASR error: {err}")
                if frame.get("msg_type") == MSG_SERVER_FULL:
                    text = _extract_text(frame)
                    if text:
                        final_text = text

        if buffer:
            frames, _ = decode_frames(buffer)
            for frame in frames:
                if frame.get("msg_type") == MSG_SERVER_FULL:
                    text = _extract_text(frame)
                    if text:
                        final_text = text

        if not final_text:
            raise RuntimeError(
                "ASR returned empty transcript (no speech detected; speak louder or longer)"
            )
        return final_text


def transcribe_wav(audio_bytes: bytes) -> str:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(transcribe_wav_async(audio_bytes))
    raise RuntimeError("Use transcribe_wav_async inside an async context")
