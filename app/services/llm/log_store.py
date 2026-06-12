"""JSONL call log persistence."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import BASE_DIR, get_settings

logger = logging.getLogger(__name__)


def _resolve_log_path() -> Path:
    settings = get_settings()
    path = Path(settings.llm_log_path)
    if not path.is_absolute():
        path = BASE_DIR / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def append_call_log(record: dict[str, Any]) -> None:
    settings = get_settings()
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        **record,
    }
    line = json.dumps(payload, ensure_ascii=False)

    if settings.llm_log_enabled:
        log_path = _resolve_log_path()
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    else:
        logger.info("llm_call %s", line)
