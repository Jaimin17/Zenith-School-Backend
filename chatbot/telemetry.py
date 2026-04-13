import hashlib
import json
import logging
import uuid
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from sqlmodel import Session

from core.database import engine
from models import ChatbotTelemetryLog


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
    file_handler = handler
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger


_logger = _build_logger()


def create_request_id() -> str:
    return str(uuid.uuid4())


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def to_safe_json(data: dict[str, Any]) -> str:
    return json.dumps(data, default=str, ensure_ascii=True)


_CONSOLE_EVENTS = {
    "step_succeeded",
    "step_failed",
    "llm_decision",
    "llm_response",
}


def _to_console_str(value: Any, max_len: int = 220) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        text = to_safe_json({"value": value})
        text = text[len('{"value":'):-1].strip() if text.startswith('{"value":') else text
    text = " ".join(text.split())
    if len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text


def _emit_console_step_log(payload: dict[str, Any]) -> None:
    event = str(payload.get("event", ""))
    if event not in _CONSOLE_EVENTS:
        return

    request_id = str(payload.get("request_id", ""))
    request_short = request_id[:8] if request_id else "-"
    if event in {"step_succeeded", "step_failed"}:
        step_id = str(payload.get("step_id", "-"))
        tool = str(payload.get("tool", "-"))
        duration_ms = payload.get("duration_ms")
        duration_part = f" | {duration_ms}ms" if duration_ms is not None else ""
        base = f"[chatbot:{request_short}] {event} | step={step_id} | tool={tool}{duration_part}"

        output_preview = _to_console_str(payload.get("output_preview"))
        error = _to_console_str(payload.get("error"))
        reason = _to_console_str(payload.get("reason"))

        if output_preview:
            base += f" | output={output_preview}"
        if error:
            base += f" | error={error}"
        if reason:
            base += f" | reason={reason}"
        print(base)
        return

    if event == "llm_decision":
        decision_type = _to_console_str(payload.get("decision_type"))
        decomposition_mode = _to_console_str(payload.get("decomposition_mode"))
        reasoning = _to_console_str(payload.get("reasoning"))
        print(
            f"[chatbot:{request_short}] llm_decision | type={decision_type or '-'} "
            f"| decomposition={decomposition_mode or '-'} | reasoning={reasoning or '-'}"
        )
        return

    if event == "llm_response":
        response_chars = _to_console_str(payload.get("response_chars"))
        response_preview = _to_console_str(payload.get("response_preview"))
        route = _to_console_str(payload.get("route"))
        source = _to_console_str(payload.get("source"))
        print(
            f"[chatbot:{request_short}] llm_response | route={route or '-'} | source={source or '-'} "
            f"| chars={response_chars or '0'} | preview={response_preview or '-'}"
        )


def _persist_event_to_db(payload: dict[str, Any]) -> None:
    try:
        with Session(engine) as session:
            payload_json = to_safe_json(payload)
            log_row = ChatbotTelemetryLog(
                created_at=datetime.utcnow(),
                request_id=str(payload.get("request_id", "")),
                event=str(payload.get("event", "unknown")),
                level=str(payload.get("level", "INFO")),
                source="chatbot",
                payload_json=json.loads(payload_json),
                hash_key=stable_hash(payload_json),
                is_delete=False,
            )
            session.add(log_row)
            session.commit()
    except Exception as exc:
        _logger.warning(to_safe_json({"event": "telemetry_db_write_failed", "error": str(exc)}))


def log_event(event: str, request_id: str, level: str = "INFO", **fields: Any) -> None:
    payload = {
        "event": event,
        "request_id": request_id,
        "level": level.upper(),
        **fields,
    }

    _emit_console_step_log(payload)
    log_method = getattr(_logger, level.lower(), _logger.info)
    log_method(to_safe_json(payload))
    _persist_event_to_db(payload)
