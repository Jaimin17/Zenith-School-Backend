from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
import re

from chatbot.ollama_health import (
    is_ollama_connection_error,
    is_ollama_reachable,
    offline_message,
    resolve_ollama_host_port,
    unreachable_message,
)
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
    @staticmethod
    def _extract_placeholders(sql: str) -> list[str]:
        found: list[str] = []
        found.extend(re.findall(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}", sql))
        found.extend(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", sql))
        return list(dict.fromkeys(found))

    @staticmethod
    def _is_objective_ref_placeholder(name: str) -> bool:
        return bool(re.fullmatch(r"obj[-_]?\d+\.[a-z_][a-z0-9_]*", str(name).strip().lower()))

    @staticmethod
    def _to_camel_case(name: str) -> str:
        parts = [p for p in name.split("_") if p]
        if not parts:
            return name
        return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])

    @staticmethod
    def _candidate_field_names(field: str, placeholder: str) -> list[str]:
        # Build a compact alias list to handle common cross-objective name mismatches
        # such as teacher_id -> id or teacherId.
        raw = str(field or "").strip()
        token = str(placeholder or "").strip()

        seeds = [name for name in [raw, token] if name]
        candidates: list[str] = []

        def add(name: str) -> None:
            n = name.strip()
            if n and n not in candidates:
                candidates.append(n)

        for seed in seeds:
            add(seed)
            if "." in seed:
                add(seed.split(".")[-1])

            snake = seed.replace("-", "_")
            add(snake)
            add(snake.lower())
            add(SqlToolAdapter._to_camel_case(snake.lower()))

            if snake.lower().endswith("_id"):
                entity = snake[:-3]
                add(entity)
                add(entity.lower())
                add(SqlToolAdapter._to_camel_case(entity.lower()))
                add("id")

        return candidates

    @staticmethod
    def _resolve_binding_value(source_rows: Any, field: str, placeholder: str) -> Any:
        candidates = SqlToolAdapter._candidate_field_names(field, placeholder)
        if isinstance(source_rows, list):
            for row in source_rows:
                if not isinstance(row, dict):
                    continue

                key_map = {str(k).lower(): k for k in row.keys()}
                for candidate in candidates:
                    key = key_map.get(candidate.lower())
                    if key is not None and row.get(key) is not None:
                        return row[key]
        return None

    @staticmethod
    def _apply_sql_bindings(sql: str, sql_bindings: dict[str, Any]) -> tuple[str, list[str]]:
        patched = sql
        unresolved: list[str] = []

        if not isinstance(sql_bindings, dict):
            sql_bindings = {}

        for placeholder, spec in sql_bindings.items():
            field = placeholder
            source_rows = None

            if isinstance(spec, dict):
                field = str(spec.get("field") or placeholder)
                source_rows = spec.get("rows")
                if source_rows is None:
                    source_rows = spec.get("payload")
                if source_rows is None:
                    source_rows = spec.get("value")
            else:
                source_rows = spec

            value = SqlToolAdapter._resolve_binding_value(source_rows, field, str(placeholder))
            placeholder_text = str(placeholder)
            token = "{" + placeholder_text + "}"
            token_double = "{{" + placeholder_text + "}}"
            if value is None:
                if token in patched or token_double in patched:
                    unresolved.append(placeholder_text)
                continue

            patched = re.sub(
                rf"\{{\{{\s*{re.escape(placeholder_text)}\s*\}}\}}",
                str(value),
                patched,
            )
            patched = re.sub(
                rf"\{{\s*{re.escape(placeholder_text)}\s*\}}",
                str(value),
                patched,
            )

        for leftover in SqlToolAdapter._extract_placeholders(patched):
            if leftover not in unresolved:
                unresolved.append(leftover)

        return patched, unresolved

    def execute(self, context: dict[str, Any], resolved_inputs: dict[str, Any]) -> ToolResult:
        sql = str(resolved_inputs.get("sql", "")).strip()
        if not sql:
            return ToolResult(status="failed", error="Missing SQL input for sql tool.")

        sql_bindings = resolved_inputs.get("sql_bindings")
        sql, unresolved = self._apply_sql_bindings(sql, sql_bindings)
        if unresolved:
            bindings = sql_bindings if isinstance(sql_bindings, dict) else {}
            unresolved_objective_refs = [
                name for name in unresolved if self._is_objective_ref_placeholder(name)
            ]
            unresolved_objective_refs_with_empty_source = []
            for name in unresolved_objective_refs:
                spec = bindings.get(name)
                if not isinstance(spec, dict):
                    continue
                source_rows = spec.get("rows")
                if source_rows is None:
                    source_rows = spec.get("payload")
                if source_rows is None:
                    source_rows = spec.get("value")
                if isinstance(source_rows, list) and len(source_rows) == 0:
                    unresolved_objective_refs_with_empty_source.append(name)

            if unresolved_objective_refs_with_empty_source and len(unresolved_objective_refs_with_empty_source) == len(unresolved):
                return ToolResult(
                    status="ok",
                    payload=[],
                    metadata={
                        "row_count": 0,
                        "empty_dependency": True,
                        "unresolved_placeholders": sorted(set(unresolved_objective_refs_with_empty_source)),
                    },
                )

            return ToolResult(
                status="failed",
                error=(
                    "Unresolved SQL placeholders: "
                    + ", ".join(sorted(set(unresolved)))
                ),
                metadata={"unresolved_placeholders": sorted(set(unresolved))},
            )

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
    def _derive_query_from_rows(rows: Any, field: str | None, db_file_field: str | None, fallback: str) -> str:
        if not isinstance(rows, list) or not rows:
            return fallback

        candidates: list[str] = []
        if db_file_field:
            candidates.append(db_file_field)
        if field and field not in candidates:
            candidates.append(field)
        candidates.extend([
            "pdf_name",
            "attachment",
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
                db_file_field = query_from_sql.get("db_file_field")
                fallback = str(query_from_sql.get("fallback", "")).strip()
                prefix = str(query_from_sql.get("prefix", "")).strip()

                derived = self._derive_query_from_rows(
                    rows,
                    str(field) if field else None,
                    str(db_file_field) if db_file_field else None,
                    fallback,
                )
                query = f"{prefix} {derived}".strip() if prefix else derived

        if not query:
            return ToolResult(status="failed", error="Missing query input for vector tool.")

        k = int(resolved_inputs.get("k", 4))
        if not is_ollama_reachable():
            host, port = resolve_ollama_host_port()
            return ToolResult(
                status="failed",
                error=offline_message(),
                metadata={"k": k, "query": query, "ollama_host": host, "ollama_port": port},
            )

        try:
            docs = search_documents(
                query,
                k=k,
                request_id=context.get("request_id"),
                subtask_id=context.get("step_id"),
            )
        except Exception as exc:
            if is_ollama_connection_error(exc):
                host, port = resolve_ollama_host_port()
                return ToolResult(
                    status="failed",
                    error=unreachable_message(),
                    metadata={"k": k, "query": query, "ollama_host": host, "ollama_port": port},
                )
            return ToolResult(status="failed", error=str(exc), metadata={"k": k, "query": query})

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
