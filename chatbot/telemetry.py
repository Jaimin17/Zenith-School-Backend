import hashlib
import json
import logging
import uuid
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from sqlmodel import Session
from sqlalchemy import text

from core.database import engine


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


_DB_INSERT_SQL = text(
    """
    INSERT INTO chatbot_telemetry_log
    (id, created_at, request_id, event, level, source, payload_json, hash_key, is_delete)
    VALUES
    (:id, :created_at, :request_id, :event, :level, :source, CAST(:payload_json AS JSON), :hash_key, :is_delete)
    """
)


def create_request_id() -> str:
    return str(uuid.uuid4())


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def to_safe_json(data: dict[str, Any]) -> str:
    return json.dumps(data, default=str, ensure_ascii=True)


def _persist_event_to_db(payload: dict[str, Any]) -> None:
    try:
        with Session(engine) as session:
            session.exec(
                _DB_INSERT_SQL,
                {
                    "id": str(uuid.uuid4()),
                    "created_at": datetime.utcnow(),
                    "request_id": str(payload.get("request_id", "")),
                    "event": str(payload.get("event", "unknown")),
                    "level": "INFO",
                    "source": "chatbot",
                    "payload_json": to_safe_json(payload),
                    "hash_key": stable_hash(to_safe_json(payload)),
                    "is_delete": False,
                },
            )
            session.commit()
    except Exception as exc:
        _logger.warning(to_safe_json({"event": "telemetry_db_write_failed", "error": str(exc)}))


def log_event(event: str, request_id: str, **fields: Any) -> None:
    payload = {
        "event": event,
        "request_id": request_id,
        **fields,
    }
    _logger.info(to_safe_json(payload))
    _persist_event_to_db(payload)
