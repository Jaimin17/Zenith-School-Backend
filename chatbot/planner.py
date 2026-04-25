from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any
import re


DEFAULT_ALLOWED_TOOLS = {"sql", "vector"}


class PlanValidationError(ValueError):
    """Raised when a generated plan is invalid or unsafe to execute."""


@dataclass
class PlanStep:
    step_id: str
    tool: str
    inputs: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    failure_mode: str = "continue"


@dataclass
class Plan:
    steps: list[PlanStep]


def _extract_ref_step_ids(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, dict):
        ref_step = value.get("ref")
        if isinstance(ref_step, str):
            refs.add(ref_step)
        for nested in value.values():
            refs.update(_extract_ref_step_ids(nested))
    elif isinstance(value, list):
        for item in value:
            refs.update(_extract_ref_step_ids(item))
    return refs


def _compute_topological_levels(steps: list[PlanStep]) -> list[list[str]]:
    step_map = {s.step_id: s for s in steps}
    indegree: dict[str, int] = {step_id: 0 for step_id in step_map}
    graph: dict[str, list[str]] = {step_id: [] for step_id in step_map}

    for step in steps:
        for dep in step.depends_on:
            graph[dep].append(step.step_id)
            indegree[step.step_id] += 1

    queue: deque[str] = deque([node for node, deg in indegree.items() if deg == 0])
    levels: list[list[str]] = []
    visited = 0

    while queue:
        current_level: list[str] = list(queue)
        queue.clear()
        levels.append(current_level)

        for node in current_level:
            visited += 1
            for neighbor in graph[node]:
                indegree[neighbor] -= 1
                if indegree[neighbor] == 0:
                    queue.append(neighbor)

    if visited != len(steps):
        raise PlanValidationError("Plan has cyclic dependencies.")

    return levels


def validate_plan(
    plan: Plan,
    max_steps: int,
    allowed_tools: set[str] | None = None,
) -> list[list[str]]:
    if not plan.steps:
        raise PlanValidationError("Plan must contain at least one step.")

    if len(plan.steps) > max_steps:
        raise PlanValidationError(f"Plan exceeds max step limit ({max_steps}).")

    allowed = allowed_tools or DEFAULT_ALLOWED_TOOLS
    step_ids = [s.step_id for s in plan.steps]
    step_id_set = set(step_ids)

    if len(step_id_set) != len(step_ids):
        raise PlanValidationError("Duplicate step_id found in plan.")

    for step in plan.steps:
        if step.tool not in allowed:
            raise PlanValidationError(f"Unsupported tool '{step.tool}' in step '{step.step_id}'.")

        missing_deps = [dep for dep in step.depends_on if dep not in step_id_set]
        if missing_deps:
            raise PlanValidationError(
                f"Step '{step.step_id}' has unknown dependencies: {missing_deps}."
            )

        if step.failure_mode not in {"continue", "stop"}:
            raise PlanValidationError(
                f"Step '{step.step_id}' has unsupported failure_mode '{step.failure_mode}'."
            )

        ref_steps = _extract_ref_step_ids(step.inputs)
        unknown_refs = [ref for ref in ref_steps if ref not in step_id_set]
        if unknown_refs:
            raise PlanValidationError(
                f"Step '{step.step_id}' has unknown input refs: {unknown_refs}."
            )

    return _compute_topological_levels(plan.steps)


def build_plan_from_decision(objective: str, decision: dict[str, Any], prefix: str = "main") -> Plan:
    steps: list[PlanStep] = []
    sql_step_id = f"{prefix}-sql"
    has_sql_step = False

    if decision.get("type") in {"sql", "both"} and decision.get("sql"):
        has_sql_step = True
        steps.append(
            PlanStep(
                step_id=sql_step_id,
                tool="sql",
                inputs={"sql": decision["sql"], "objective": objective},
            )
        )

    if decision.get("type") in {"doc", "both"} and decision.get("search_phrase"):
        search_phrase = decision.get("search_phrase") or objective
        vector_from_sql_field = decision.get("vector_from_sql_field")
        db_file_field = decision.get("db_file_field")

        depends_on: list[str] = []
        vector_inputs: dict[str, Any]
        if has_sql_step and (vector_from_sql_field or db_file_field):
            depends_on = [sql_step_id]
            vector_inputs = {
                "k": 4,
                "query_from_sql": {
                    "rows": {"ref": sql_step_id, "path": "payload"},
                    "field": vector_from_sql_field,
                    "db_file_field": db_file_field,
                    "prefix": decision.get("vector_prefix") or "",
                    "fallback": search_phrase,
                },
                "objective": objective,
            }
        else:
            vector_inputs = {"query": search_phrase, "k": 4, "objective": objective}

        steps.append(
            PlanStep(
                step_id=f"{prefix}-vector",
                tool="vector",
                inputs=vector_inputs,
                depends_on=depends_on,
            )
        )

    return Plan(steps=steps)


def build_plan_from_objectives(objectives: list[str], decisions: list[dict[str, Any]]) -> Plan:
    steps: list[PlanStep] = []
    sql_steps_by_index: dict[int, str] = {}

    def _coerce_obj_index(raw: Any) -> int | None:
        if raw is None:
            return None
        text = str(raw).strip().lower()
        if not text:
            return None
        match = re.search(r"(\d+)", text)
        if not match:
            return None
        idx = int(match.group(1))
        return idx if idx >= 1 else None

    def _extract_placeholders(sql: str) -> list[str]:
        found: list[str] = []
        found.extend(re.findall(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}", sql))
        found.extend(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", sql))
        return list(dict.fromkeys(found))

    def _parse_objective_ref(token: str) -> tuple[int, str] | None:
        text = str(token or "").strip().lower()
        match = re.fullmatch(r"obj[-_]?(\d+)\.([a-z_][a-z0-9_]*)", text)
        if not match:
            return None
        idx = int(match.group(1))
        field = match.group(2)
        if idx < 1 or not field:
            return None
        return idx, field

    for index, objective in enumerate(objectives, start=1):
        decision = decisions[index - 1]
        prefix = f"obj-{index}"
        sql_step_id = f"{prefix}-sql"
        sql_text = decision.get("sql")

        sql_depends_on: list[str] = []
        sql_bindings: dict[str, Any] = {}

        def _add_sql_dependency(step_id: str) -> None:
            if step_id not in sql_depends_on:
                sql_depends_on.append(step_id)

        declared_dep_index = _coerce_obj_index(decision.get("depends_on_objective"))
        has_declared_dep = (
            declared_dep_index is not None
            and declared_dep_index < index
            and declared_dep_index in sql_steps_by_index
        )
        dep_index = declared_dep_index if has_declared_dep else None

        if dep_index is None and isinstance(sql_text, str):
            placeholders = _extract_placeholders(sql_text)
            objective_ref_indices = [
                parsed[0]
                for parsed in (_parse_objective_ref(token) for token in placeholders)
                if parsed and parsed[0] < index and parsed[0] in sql_steps_by_index
            ]
            if objective_ref_indices:
                dep_index = objective_ref_indices[-1]

            if placeholders:
                if dep_index is None:
                    for prev_idx in range(index - 1, 0, -1):
                        if prev_idx in sql_steps_by_index:
                            dep_index = prev_idx
                            break

        if dep_index is not None:
            dep_step_id = sql_steps_by_index[dep_index]
            _add_sql_dependency(dep_step_id)

        if isinstance(sql_text, str):
            placeholders = _extract_placeholders(sql_text)
            for field_name in placeholders:
                parsed_ref = _parse_objective_ref(field_name)
                if parsed_ref:
                    ref_idx, ref_field = parsed_ref
                    ref_step_id = sql_steps_by_index.get(ref_idx)
                    if ref_step_id and ref_idx < index:
                        _add_sql_dependency(ref_step_id)
                        sql_bindings[field_name] = {
                            "ref": ref_step_id,
                            "path": "payload",
                            "field": ref_field,
                        }
                    continue

                if sql_depends_on:
                    sql_bindings[field_name] = {
                        "ref": sql_depends_on[0],
                        "path": "payload",
                        "field": field_name.split(".")[-1],
                    }

        if decision.get("type") in {"sql", "both"} and decision.get("sql"):
            steps.append(
                PlanStep(
                    step_id=sql_step_id,
                    tool="sql",
                    inputs={
                        "sql": decision["sql"],
                        "objective": objective,
                        "sql_bindings": sql_bindings,
                    },
                    depends_on=sql_depends_on,
                )
            )
            sql_steps_by_index[index] = sql_step_id

        should_add_vector = decision.get("type") in {"doc", "both"}
        if decision.get("type") == "both" and not decision.get("needs_docs", False) and decision.get("sql"):
            should_add_vector = False

        if should_add_vector:
            search_phrase = decision.get("search_phrase") or objective
            vector_from_sql_field = decision.get("vector_from_sql_field")
            db_file_field = decision.get("db_file_field")

            depends_on: list[str] = []
            vector_inputs: dict[str, Any]
            if (vector_from_sql_field or db_file_field) and any(s.step_id == sql_step_id for s in steps):
                depends_on = [sql_step_id]
                vector_inputs = {
                    "k": 4,
                    "query_from_sql": {
                        "rows": {"ref": sql_step_id, "path": "payload"},
                        "field": vector_from_sql_field,
                        "db_file_field": db_file_field,
                        "prefix": decision.get("vector_prefix") or "",
                        "fallback": search_phrase,
                    },
                }
            else:
                vector_inputs = {"query": search_phrase, "k": 4}

            steps.append(
                PlanStep(
                    step_id=f"{prefix}-vector",
                    tool="vector",
                    inputs=vector_inputs,
                    depends_on=depends_on,
                )
            )

    return Plan(steps=steps)
