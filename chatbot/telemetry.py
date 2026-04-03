import hashlib
import json
import logging
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


_LOGGER_NAME = "chatbot.telemetry"
_MAX_LOG_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 5


def _build_logger() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "chatbot-telemetry.log"

    handler = RotatingFileHandler(
        log_file,
        maxBytes=_MAX_LOG_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


_logger = _build_logger()


def create_request_id() -> str:
    return str(uuid.uuid4())


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def to_safe_json(data: dict[str, Any]) -> str:
    return json.dumps(data, default=str, ensure_ascii=True)


def log_event(event: str, request_id: str, **fields: Any) -> None:
    payload = {
        "event": event,
        "request_id": request_id,
        **fields,
    }
    _logger.info(to_safe_json(payload))
