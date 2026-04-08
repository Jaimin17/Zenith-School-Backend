from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from chatbot.sql_executor import execute_sql_query
from chatbot.vector_search import search_documents


@dataclass
class ToolResult:
    status: str
    payload: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class ToolAdapter(Protocol):
    def execute(self, context: dict[str, Any], resolved_inputs: dict[str, Any]) -> ToolResult:
        ...


class SqlToolAdapter:
    def execute(self, context: dict[str, Any], resolved_inputs: dict[str, Any]) -> ToolResult:
        sql = str(resolved_inputs.get("sql", "")).strip()
        if not sql:
            return ToolResult(status="failed", error="Missing SQL input for sql tool.")

        rows = execute_sql_query(
            sql,
            context["session"],
            request_id=context.get("request_id"),
            subtask_id=context.get("step_id"),
        )

        if rows and isinstance(rows, list) and isinstance(rows[0], dict) and rows[0].get("error"):
            return ToolResult(status="failed", payload=rows, error=rows[0]["error"])

        return ToolResult(
            status="ok",
            payload=rows,
            metadata={"row_count": len(rows) if isinstance(rows, list) else 0},
        )


class VectorToolAdapter:
    @staticmethod
    def _derive_query_from_rows(rows: Any, field: str | None, fallback: str) -> str:
        if not isinstance(rows, list) or not rows:
            return fallback

        candidates = [field] if field else []
        candidates.extend([
            "title",
            "name",
            "assignment_title",
            "filename",
            "file_name",
            "subject_name",
        ])

        values: list[str] = []
        for row in rows[:3]:
            if not isinstance(row, dict):
                continue
            for key in candidates:
                if not key:
                    continue
                val = row.get(key)
                if val is not None and str(val).strip():
                    values.append(str(val).strip())
                    break

        if values:
            return " ".join(values)
        return fallback

    def execute(self, context: dict[str, Any], resolved_inputs: dict[str, Any]) -> ToolResult:
        query = str(resolved_inputs.get("query", "")).strip()

        if not query:
            query_from_sql = resolved_inputs.get("query_from_sql")
            if isinstance(query_from_sql, dict):
                rows = query_from_sql.get("rows")
                field = query_from_sql.get("field")
                fallback = str(query_from_sql.get("fallback", "")).strip()
                prefix = str(query_from_sql.get("prefix", "")).strip()

                derived = self._derive_query_from_rows(rows, str(field) if field else None, fallback)
                query = f"{prefix} {derived}".strip() if prefix else derived

        if not query:
            return ToolResult(status="failed", error="Missing query input for vector tool.")

        k = int(resolved_inputs.get("k", 4))
        docs = search_documents(
            query,
            k=k,
            request_id=context.get("request_id"),
            subtask_id=context.get("step_id"),
        )

        return ToolResult(
            status="ok",
            payload=docs,
            metadata={"k": k, "chars": len(docs)},
        )


class ToolRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, ToolAdapter] = {}

    def register(self, tool_name: str, adapter: ToolAdapter) -> None:
        self._registry[tool_name] = adapter

    def get(self, tool_name: str) -> ToolAdapter:
        if tool_name not in self._registry:
            raise KeyError(f"No adapter registered for tool '{tool_name}'.")
        return self._registry[tool_name]


def create_default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register("sql", SqlToolAdapter())
    registry.register("vector", VectorToolAdapter())
    return registry
