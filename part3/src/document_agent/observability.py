from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
from typing import Any, TextIO


PART3_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_PATH = PART3_ROOT / "logs" / "document_agent.log"
LOGGER_NAME = "document_agent"
MAX_LOG_BYTES = 1_000_000
LOG_BACKUP_COUNT = 3


class JsonEventFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=timezone.utc,
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event_name", record.getMessage()),
        }
        payload.update(getattr(record, "event_fields", {}))
        return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def configure_logging(
    log_path: Path | str = DEFAULT_LOG_PATH,
    *,
    stream: TextIO | None = sys.stderr,
) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if any(getattr(handler, "_document_agent_handler", False) for handler in logger.handlers):
        return logger

    formatter = JsonEventFormatter()
    if stream is not None:
        stream_handler = logging.StreamHandler(stream)
        stream_handler.setFormatter(formatter)
        stream_handler._document_agent_handler = True  # type: ignore[attr-defined]
        logger.addHandler(stream_handler)

    destination = Path(log_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        destination,
        maxBytes=MAX_LOG_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler._document_agent_handler = True  # type: ignore[attr-defined]
    logger.addHandler(file_handler)
    return logger


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    logger.log(
        level,
        event,
        extra={
            "event_name": event,
            "event_fields": fields,
        },
    )
