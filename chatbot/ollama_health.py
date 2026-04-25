from __future__ import annotations

import os
import socket
from urllib.parse import urlparse


def resolve_ollama_host_port() -> tuple[str, int]:
    raw = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").strip()
    if "//" not in raw:
        raw = "http://" + raw
    parsed = urlparse(raw)
    host = parsed.hostname or "127.0.0.1"
    port = int(parsed.port or 11434)
    return host, port


def is_ollama_reachable(timeout_sec: float = 0.4) -> bool:
    host, port = resolve_ollama_host_port()
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True
    except OSError:
        return False


def is_ollama_connection_error(error: Exception) -> bool:
    text = str(error).lower()
    return any(
        marker in text
        for marker in [
            "failed to connect to ollama",
            "connection refused",
            "max retries exceeded",
            "could not connect",
        ]
    )


def offline_message() -> str:
    host, port = resolve_ollama_host_port()
    return (
        "Document retrieval is temporarily unavailable because Ollama is offline "
        f"at {host}:{port}. Start Ollama and retry."
    )


def unreachable_message() -> str:
    host, port = resolve_ollama_host_port()
    return (
        "Document retrieval failed because Ollama is unreachable "
        f"at {host}:{port}. Start Ollama and retry."
    )
