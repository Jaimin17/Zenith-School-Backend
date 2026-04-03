from sqlmodel import Session, text
from core.database import SessionDep
import re
import time

from chatbot.telemetry import log_event, stable_hash

# Hard block dangerous keywords — safety net even if LLM slips
BLOCKED_KEYWORDS = ["drop", "delete", "update", "insert", "alter", "truncate", "create"]
MAX_ROWS = 100
QUERY_TIMEOUT_MS = 5000


def is_safe_query(sql: str) -> bool:
    sql_lower = sql.lower()
    for keyword in BLOCKED_KEYWORDS:
        # Use word boundary to avoid false positives
        if re.search(rf'\b{keyword}\b', sql_lower):
            return False
    return True


def execute_sql_query(sql: str, session: SessionDep, request_id: str | None = None, subtask_id: str | None = None) -> list[dict]:
    """
    Safely execute a read-only SQL query and return results as list of dicts.
    """
    started = time.perf_counter()

    if not is_safe_query(sql):
        if request_id:
            log_event(
                "sql_blocked",
                request_id,
                subtask_id=subtask_id,
                sql_hash=stable_hash(sql),
            )
        return [{"error": "Query blocked for safety reasons."}]

    try:
        session.exec(text("SET statement_timeout = '5s'"))
        sql_with_limit = sql.rstrip(";") + f" LIMIT {MAX_ROWS};"
        result = session.exec(text(sql_with_limit))
        rows = result.fetchall()
        columns = result.keys()
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        if request_id:
            log_event(
                "sql_success",
                request_id,
                subtask_id=subtask_id,
                sql_hash=stable_hash(sql_with_limit),
                row_count=len(rows),
                duration_ms=duration_ms,
            )
        # Convert to list of dicts so it's readable
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        if request_id:
            log_event(
                "sql_error",
                request_id,
                subtask_id=subtask_id,
                sql_hash=stable_hash(sql),
                duration_ms=duration_ms,
                error=str(e),
            )
        return [{"error": f"SQL error: {str(e)}"}]
