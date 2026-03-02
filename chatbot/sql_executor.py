from sqlmodel import Session, text
from core.database import SessionDep
import re

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


def execute_sql_query(sql: str, session: SessionDep) -> list[dict]:
    """
    Safely execute a read-only SQL query and return results as list of dicts.
    """
    if not is_safe_query(sql):
        return [{"error": "Query blocked for safety reasons."}]

    try:
        session.exec(text("SET statement_timeout = '5s'"))
        sql_with_limit = sql.rstrip(";") + f" LIMIT {MAX_ROWS};"
        result = session.exec(text(sql_with_limit))
        rows = result.fetchall()
        columns = result.keys()
        # Convert to list of dicts so it's readable
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        return [{"error": f"SQL error: {str(e)}"}]
