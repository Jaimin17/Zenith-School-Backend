from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any


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

    if decision.get("type") in {"sql", "both"} and decision.get("sql"):
        steps.append(
            PlanStep(
                step_id=f"{prefix}-sql",
                tool="sql",
                inputs={"sql": decision["sql"], "objective": objective},
            )
        )

    if decision.get("type") in {"doc", "both"} and decision.get("search_phrase"):
        steps.append(
            PlanStep(
                step_id=f"{prefix}-vector",
                tool="vector",
                inputs={"query": decision["search_phrase"], "k": 4, "objective": objective},
            )
        )

    return Plan(steps=steps)


def build_plan_from_objectives(objectives: list[str], decisions: list[dict[str, Any]]) -> Plan:
    steps: list[PlanStep] = []

    for index, objective in enumerate(objectives, start=1):
        decision = decisions[index - 1]
        prefix = f"obj-{index}"
        sql_step_id = f"{prefix}-sql"

        if decision.get("type") in {"sql", "both"} and decision.get("sql"):
            steps.append(
                PlanStep(
                    step_id=sql_step_id,
                    tool="sql",
                    inputs={"sql": decision["sql"], "objective": objective},
                )
            )

        if decision.get("type") in {"doc", "both"}:
            search_phrase = decision.get("search_phrase") or objective
            vector_from_sql_field = decision.get("vector_from_sql_field")

            depends_on: list[str] = []
            vector_inputs: dict[str, Any]
            if vector_from_sql_field and any(s.step_id == sql_step_id for s in steps):
                depends_on = [sql_step_id]
                vector_inputs = {
                    "k": 4,
                    "query_from_sql": {
                        "rows": {"ref": sql_step_id, "path": "payload"},
                        "field": vector_from_sql_field,
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
