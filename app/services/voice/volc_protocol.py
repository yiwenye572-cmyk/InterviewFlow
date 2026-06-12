"""Volcengine openspeech binary frame codec (ASR sauc v3)."""

from __future__ import annotations

import gzip
import json
import struct
from typing import Any

MSG_FULL_CLIENT = 0x1
MSG_AUDIO_ONLY = 0x2
MSG_SERVER_FULL = 0x9
MSG_SERVER_ERROR = 0xF

FLAG_NONE = 0x0
FLAG_POS_SEQ = 0x1
FLAG_LAST_NO_SEQ = 0x2
FLAG_NEG_SEQ = 0x3

SERIAL_NONE = 0x0
SERIAL_JSON = 0x1

COMPRESS_NONE = 0x0
COMPRESS_GZIP = 0x1


def _header(
    msg_type: int,
    flags: int = FLAG_NONE,
    serialization: int = SERIAL_JSON,
    compression: int = COMPRESS_NONE,
) -> bytes:
    return bytes(
        [
            (0x1 << 4) | 0x1,
            (msg_type << 4) | (flags & 0xF),
            (serialization << 4) | (compression & 0xF),
            0x00,
        ]
    )


def encode_frame(
    msg_type: int,
    payload: bytes,
    *,
    flags: int = FLAG_NONE,
    serialization: int = SERIAL_JSON,
    compression: int = COMPRESS_NONE,
    sequence: int | None = None,
) -> bytes:
    body = gzip.compress(payload) if compression == COMPRESS_GZIP and payload else payload

    parts = [_header(msg_type, flags, serialization, compression)]
    if flags in (FLAG_POS_SEQ, FLAG_NEG_SEQ) and sequence is not None:
        parts.append(struct.pack(">i", sequence))
    parts.append(struct.pack(">I", len(body)))
    parts.append(body)
    return b"".join(parts)


def decode_frames(buffer: bytes) -> tuple[list[dict[str, Any]], bytes]:
    messages: list[dict[str, Any]] = []
    offset = 0
    while offset + 4 <= len(buffer):
        header = buffer[offset : offset + 4]
        msg_type = header[1] >> 4
        flags = header[1] & 0xF
        serialization = header[2] >> 4
        compression = header[2] & 0xF
        offset += 4

        sequence = None
        error_code = None
        if flags in (FLAG_POS_SEQ, FLAG_NEG_SEQ):
            if offset + 4 > len(buffer):
                offset -= 4
                break
            sequence = struct.unpack(">i", buffer[offset : offset + 4])[0]
            offset += 4

        if msg_type == MSG_SERVER_ERROR:
            if offset + 4 > len(buffer):
                offset -= 4
                if sequence is not None:
                    offset -= 4
                break
            error_code = struct.unpack(">I", buffer[offset : offset + 4])[0]
            offset += 4

        if offset + 4 > len(buffer):
            offset -= 4
            if sequence is not None:
                offset -= 4
            if error_code is not None:
                offset -= 4
            break

        payload_size = struct.unpack(">I", buffer[offset : offset + 4])[0]
        offset += 4
        if offset + payload_size > len(buffer):
            offset -= 4
            if sequence is not None:
                offset -= 4
            if error_code is not None:
                offset -= 4
            offset -= 4
            break

        payload = buffer[offset : offset + payload_size]
        offset += payload_size

        if compression == COMPRESS_GZIP and payload:
            payload = gzip.decompress(payload)

        parsed: dict[str, Any] = {
            "msg_type": msg_type,
            "flags": flags,
            "sequence": sequence,
            "error_code": error_code,
        }
        if msg_type == MSG_SERVER_ERROR:
            try:
                parsed["error"] = json.loads(payload.decode("utf-8"))
            except Exception:
                parsed["error_raw"] = payload
        elif serialization == SERIAL_JSON and payload:
            try:
                parsed["json"] = json.loads(payload.decode("utf-8"))
            except Exception:
                parsed["raw"] = payload
        else:
            parsed["raw"] = payload
        messages.append(parsed)

    return messages, buffer[offset:]
