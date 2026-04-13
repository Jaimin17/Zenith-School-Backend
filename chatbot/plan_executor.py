from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from chatbot.planner import Plan, PlanStep
from chatbot.telemetry import log_event
from chatbot.tool_registry import ToolRegistry, ToolResult


@dataclass
class StepExecutionRecord:
    step_id: str
    tool: str
    status: str
    payload: Any = None
    metadata: dict[str, Any] | None = None
    error: str | None = None
    duration_ms: float = 0.0
    depends_on: list[str] | None = None


@dataclass
class ExecutionReport:
    records: list[StepExecutionRecord]


def _preview_step_output(payload: Any, max_len: int = 220) -> str:
    if payload is None:
        return ""
    text = str(payload)
    text = " ".join(text.split())
    if len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text


def _resolve_input_value(value: Any, results: dict[str, StepExecutionRecord]) -> Any:
    if isinstance(value, dict):
        if "ref" in value:
            ref_step = value["ref"]
            if ref_step not in results:
                raise KeyError(f"Referenced step '{ref_step}' not found in execution context.")
            ref_path = value.get("path", "payload")
            ref_record = results[ref_step]
            return getattr(ref_record, ref_path)
        return {k: _resolve_input_value(v, results) for k, v in value.items()}

    if isinstance(value, list):
        return [_resolve_input_value(v, results) for v in value]

    return value


def _resolve_inputs(step: PlanStep, results: dict[str, StepExecutionRecord]) -> dict[str, Any]:
    return {k: _resolve_input_value(v, results) for k, v in step.inputs.items()}


async def _run_step(
    step: PlanStep,
    registry: ToolRegistry,
    shared_context: dict[str, Any],
    results: dict[str, StepExecutionRecord],
    step_timeout_ms: int,
) -> StepExecutionRecord:
    started = time.perf_counter()
    request_id = shared_context.get("request_id")

    try:
        resolved_inputs = _resolve_inputs(step, results)
    except Exception as exc:
        return StepExecutionRecord(
            step_id=step.step_id,
            tool=step.tool,
            status="failed",
            error=f"Input resolution failed: {exc}",
            depends_on=step.depends_on,
        )

    if request_id:
        log_event(
            "step_started",
            request_id,
            step_id=step.step_id,
            tool=step.tool,
            dependency_count=len(step.depends_on),
        )

    adapter = registry.get(step.tool)

    try:
        result: ToolResult = await asyncio.wait_for(
            asyncio.to_thread(
                adapter.execute,
                {**shared_context, "step_id": step.step_id},
                resolved_inputs,
            ),
            timeout=step_timeout_ms / 1000,
        )
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        if request_id:
            log_event(
                "step_failed",
                request_id,
                step_id=step.step_id,
                tool=step.tool,
                duration_ms=duration_ms,
                error=str(exc),
            )
        return StepExecutionRecord(
            step_id=step.step_id,
            tool=step.tool,
            status="failed",
            error=str(exc),
            duration_ms=duration_ms,
            depends_on=step.depends_on,
        )

    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    status = "succeeded" if result.status == "ok" else "failed"

    if request_id:
        event_name = "step_succeeded" if status == "succeeded" else "step_failed"
        log_event(
            event_name,
            request_id,
            step_id=step.step_id,
            tool=step.tool,
            duration_ms=duration_ms,
            dependency_count=len(step.depends_on),
            output_preview=_preview_step_output(result.payload),
            error=result.error,
        )

    return StepExecutionRecord(
        step_id=step.step_id,
        tool=step.tool,
        status=status,
        payload=result.payload,
        metadata=result.metadata,
        error=result.error,
        duration_ms=duration_ms,
        depends_on=step.depends_on,
    )


async def execute_plan(
    plan: Plan,
    levels: list[list[str]],
    registry: ToolRegistry,
    shared_context: dict[str, Any],
    step_timeout_ms: int,
    global_timeout_ms: int,
) -> ExecutionReport:
    started = time.perf_counter()
    request_id = shared_context.get("request_id")
    step_map = {step.step_id: step for step in plan.steps}
    records: dict[str, StepExecutionRecord] = {}

    if request_id:
        log_event("plan_created", request_id, step_count=len(plan.steps))

    for level in levels:
        elapsed_ms = (time.perf_counter() - started) * 1000
        if elapsed_ms > global_timeout_ms:
            for step_id in level:
                step = step_map[step_id]
                rec = StepExecutionRecord(
                    step_id=step_id,
                    tool=step.tool,
                    status="skipped",
                    error="Global timeout exceeded before step execution.",
                    depends_on=step.depends_on,
                )
                records[step_id] = rec
                if request_id:
                    log_event(
                        "step_skipped",
                        request_id,
                        step_id=step_id,
                        tool=step.tool,
                        reason="global_timeout",
                    )
            continue

        runnable: list[PlanStep] = []
        for step_id in level:
            step = step_map[step_id]
            failed_dependency = next(
                (dep for dep in step.depends_on if records.get(dep) and records[dep].status != "succeeded"),
                None,
            )
            if failed_dependency:
                records[step_id] = StepExecutionRecord(
                    step_id=step_id,
                    tool=step.tool,
                    status="skipped",
                    error=f"Dependency '{failed_dependency}' did not succeed.",
                    depends_on=step.depends_on,
                )
                if request_id:
                    log_event(
                        "step_skipped",
                        request_id,
                        step_id=step_id,
                        tool=step.tool,
                        reason="dependency_failed",
                        failed_dependency=failed_dependency,
                    )
                continue
            runnable.append(step)

        jobs = [
            _run_step(step, registry, shared_context, records, step_timeout_ms)
            for step in runnable
        ]
        if not jobs:
            continue

        completed = await asyncio.gather(*jobs)
        for rec in completed:
            records[rec.step_id] = rec

            if rec.status == "failed":
                step = step_map[rec.step_id]
                if step.failure_mode == "stop":
                    if request_id:
                        log_event(
                            "plan_finished",
                            request_id,
                            stopped_early=True,
                            reason=f"Step '{rec.step_id}' failed with failure_mode=stop",
                        )
                    ordered = [records[s.step_id] for s in plan.steps if s.step_id in records]
                    return ExecutionReport(records=ordered)

    ordered_records = [records[s.step_id] for s in plan.steps if s.step_id in records]
    if request_id:
        success_count = sum(1 for r in ordered_records if r.status == "succeeded")
        fail_count = sum(1 for r in ordered_records if r.status == "failed")
        skip_count = sum(1 for r in ordered_records if r.status == "skipped")
        log_event(
            "plan_finished",
            request_id,
            total_steps=len(ordered_records),
            succeeded_steps=success_count,
            failed_steps=fail_count,
            skipped_steps=skip_count,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )

    return ExecutionReport(records=ordered_records)
