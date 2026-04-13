from sqlmodel import Session
import asyncio

from chatbot.permissions import get_user_permission_context
from chatbot.classifier import (
    classify_and_generate_query,
    classify_objectives_batch,
    INTENT_OUT_OF_SCOPE,
    _assistant_scope_message_for_query,
)
from chatbot.sql_executor import execute_sql_query
from chatbot.vector_search import search_documents
from chatbot.formatter import FORMAT_PROMPT
from chatbot.plan_executor import execute_plan
from chatbot.planner import (
    PlanValidationError,
    build_plan_from_decision,
    build_plan_from_objectives,
    validate_plan,
)
from chatbot.tool_registry import create_default_tool_registry
import uuid, json
from typing import AsyncGenerator, Any
import time

from core.config import settings
from chatbot.telemetry import log_event
from chatbot.llm_factory import create_llm

# Separate LLM instance for streaming (formatter step only)
streaming_llm = create_llm(temperature=0.3, streaming=True)
MAX_DECOMPOSE_OBJECTIVES = 4


def _derive_vector_query_from_rows(
        rows: Any,
        field: str | None,
        db_file_field: str | None,
        fallback: str,
        prefix: str = "",
) -> str:
    if isinstance(rows, list):
        candidates: list[str] = []
        if db_file_field:
            candidates.append(db_file_field)
        if field and field not in candidates:
            candidates.append(field)
        candidates.extend(["pdf_name", "attachment", "title", "name", "filename", "file_name"])

        values: list[str] = []
        for row in rows[:3]:
            if not isinstance(row, dict):
                continue
            for key in candidates:
                val = row.get(key)
                if val is not None and str(val).strip():
                    values.append(str(val).strip())
                    break
        if values:
            base = " ".join(values)
            return f"{prefix} {base}".strip() if prefix else base

    return f"{prefix} {fallback}".strip() if prefix else fallback


def _resolve_data_source_from_tools(tools: set[str]) -> str:
    if tools == {"sql"}:
        return "the school database"
    if tools == {"vector"}:
        return "uploaded school documents"
    if tools:
        return "the school database and uploaded documents"
    return "no retrievable source"


def _format_plan_report(report: Any, max_chars: int) -> tuple[str, str, int]:
    sections: list[str] = []
    tools_used: set[str] = set()
    completed = 0

    for rec in report.records:
        tools_used.add(rec.tool)
        if rec.status == "succeeded":
            completed += 1

        if rec.tool == "sql":
            payload = json.dumps(rec.payload, indent=2, default=str)
            section = f"[{rec.step_id}] SQL ({rec.status})\n{payload}"
        elif rec.tool == "vector":
            payload = str(rec.payload or "")
            section = f"[{rec.step_id}] VECTOR ({rec.status})\n{payload}"
        else:
            payload = json.dumps(rec.payload, indent=2, default=str)
            section = f"[{rec.step_id}] {rec.tool.upper()} ({rec.status})\n{payload}"

        if rec.error:
            section += f"\nError: {rec.error}"

        sections.append(section)

    combined = "\n\n".join(sections)
    if len(combined) > max_chars:
        combined = combined[:max_chars] + "\n\n[truncated due to payload limit]"

    return combined, _resolve_data_source_from_tools(tools_used), completed


async def _run_objective_task(
        session: Session,
        objective: str,
        decision: dict[str, Any],
        request_id: str | None,
        index: int,
) -> dict[str, Any]:
    subtask_id = f"task-{index}"
    output: dict[str, Any] = {
        "objective": objective,
        "status": "ok",
        "sources": [],
        "section": "",
    }

    if decision.get("type") == INTENT_OUT_OF_SCOPE:
        output["status"] = "skipped"
        output["section"] = f"[Objective {index}] {objective}\nOut of scope for school assistant."
        return output

    sql_payload = ""
    doc_payload = ""

    sql_task = None
    doc_task = None

    decision_type = decision.get("type")
    if decision_type in {"sql", "both"} and decision.get("sql"):
        sql_task = asyncio.to_thread(
            execute_sql_query,
            decision["sql"],
            session,
            request_id,
            f"{subtask_id}-sql",
        )
    if decision_type in {"doc", "both"} and decision.get("search_phrase"):
        doc_task = asyncio.to_thread(
            search_documents,
            decision["search_phrase"],
            4,
            request_id,
            f"{subtask_id}-doc",
        )

    if sql_task and doc_task:
        sql_rows, docs = await asyncio.gather(sql_task, doc_task)
        sql_payload = json.dumps(sql_rows, indent=2, default=str)
        doc_payload = docs
        output["sources"] = ["database", "documents"]
        output["section"] = (
            f"[Objective {index}] {objective}\n"
            f"--- Database ---\n{sql_payload}\n\n"
            f"--- Documents ---\n{doc_payload}\n"
        )
        return output

    if sql_task:
        sql_rows = await sql_task
        sql_payload = json.dumps(sql_rows, indent=2, default=str)
        output["sources"] = ["database"]
        output["section"] = f"[Objective {index}] {objective}\n--- Database ---\n{sql_payload}\n"
        return output

    if doc_task:
        doc_payload = await doc_task
        output["sources"] = ["documents"]
        output["section"] = f"[Objective {index}] {objective}\n--- Documents ---\n{doc_payload}\n"
        return output

    output["status"] = "empty"
    output["section"] = f"[Objective {index}] {objective}\nNo executable sub-task generated."
    return output


async def run_agent_stream(session: Session, query: str, role: str, user_id: uuid.UUID, extra: dict = {},
                           chat_history: list[dict] = [], request_id: str | None = None) -> \
        AsyncGenerator[str, None]:
    """
    Full agent pipeline with streaming on the final formatting step.
    Steps 1-3 run normally (classify, fetch data).
    Step 4 (formatter) streams token by token.
    """

    started = time.perf_counter()

    # ── Step 1: Build permission context ──
    yield {"type": "stage", "value": "routing"}
    permission_ctx = get_user_permission_context(role, user_id, extra)
    if request_id:
        log_event(
            "request_started",
            request_id,
            role=str(role),
            query=query,
            chat_history_len=len(chat_history),
        )

    # ── Step 2: LLM classifies query and generates SQL or search phrase ──
    # This step does NOT stream — we need the full decision before proceeding
    decision = classify_and_generate_query(query, permission_ctx, chat_history)

    print(f"🧠 LLM Decision: {decision['reasoning']}")  # helpful for debugging
    if request_id:
        log_event(
            "classifier_decision",
            request_id,
            decision_type=decision.get("type"),
            decomposition_mode=decision.get("decomposition_mode", False),
            objective_count=len(decision.get("objectives", [])),
            reasoning=decision.get("reasoning"),
        )

    raw_data = ""
    data_source = ""

    # ── Step 3A: Generic planner execution path (feature-flagged) ──
    objectives = decision.get("objectives", [])
    objective_items = decision.get("objective_items", [{"text": o} for o in objectives])
    decomposition_mode = bool(decision.get("decomposition_mode")) and len(objectives) > 1
    planner_succeeded = False
    cached_sub_decisions: list[dict[str, Any]] | None = None
    skipped_objectives_notes: list[str] = []
    all_objectives_out_of_scope = False

    print(f"Decomposition mode: {decomposition_mode}, Objectives: {objectives}")  # helpful for debugging

    if settings.ENABLE_GENERIC_PLANNER and decision.get("type") != INTENT_OUT_OF_SCOPE:
        try:
            yield {"type": "stage", "value": "planning"}

            if decomposition_mode:
                candidate_objective_items = objective_items
                if len(candidate_objective_items) > MAX_DECOMPOSE_OBJECTIVES:
                    candidate_objective_items = candidate_objective_items[:MAX_DECOMPOSE_OBJECTIVES]
                    if request_id:
                        log_event(
                            "decomposition_truncated",
                            request_id,
                            max_objectives=MAX_DECOMPOSE_OBJECTIVES,
                            original_count=len(decision.get("objectives", [])),
                        )
                candidate_objectives = [item.get("text", "").strip() for item in candidate_objective_items if item.get("text")]

                if request_id:
                    log_event(
                        "batch_objective_planning_started",
                        request_id,
                        objective_count=len(candidate_objectives),
                    )

                sub_decisions = classify_objectives_batch(
                    query=query,
                    objectives=candidate_objective_items,
                    permission_ctx=permission_ctx,
                    chat_history=chat_history,
                )
                all_objectives_out_of_scope = bool(sub_decisions) and all(
                    dec.get("type") == INTENT_OUT_OF_SCOPE for dec in sub_decisions
                )

                cached_sub_decisions = sub_decisions
                objectives = candidate_objectives
                plan = build_plan_from_objectives(candidate_objectives, sub_decisions)

                skipped_objectives_notes = [
                    f"{i + 1}. {obj}"
                    for i, (obj, dec) in enumerate(zip(candidate_objectives, sub_decisions))
                    if dec.get("type") == INTENT_OUT_OF_SCOPE
                ]

                if request_id:
                    log_event(
                        "batch_objective_planning_completed",
                        request_id,
                        objective_count=len(candidate_objectives),
                        planned_steps=len(plan.steps),
                    )
            else:
                plan = build_plan_from_decision(query, decision)

            if not plan.steps and decomposition_mode:
                if request_id:
                    log_event("batch_objective_planning_failed", request_id, reason="empty_plan")
                sub_decisions = [
                    classify_and_generate_query(objective, permission_ctx, chat_history)
                    for objective in objectives
                ]
                cached_sub_decisions = sub_decisions
                plan = build_plan_from_objectives(objectives, sub_decisions)

            levels = validate_plan(plan, max_steps=settings.PLANNER_MAX_STEPS)

            yield {"type": "stage", "value": "plan_execute"}
            report = await execute_plan(
                plan=plan,
                levels=levels,
                registry=create_default_tool_registry(),
                shared_context={"session": session, "request_id": request_id},
                step_timeout_ms=settings.PLANNER_STEP_TIMEOUT_MS,
                global_timeout_ms=settings.PLANNER_GLOBAL_TIMEOUT_MS,
            )
            raw_data, data_source, completed = _format_plan_report(
                report,
                max_chars=settings.PLANNER_MAX_PAYLOAD_CHARS,
            )
            planner_succeeded = completed > 0
            if request_id:
                log_event(
                    "planner_route_completed",
                    request_id,
                    completed_steps=completed,
                    total_steps=len(report.records),
                    planner_succeeded=planner_succeeded,
                )
            if completed == 0:
                if decomposition_mode and all_objectives_out_of_scope:
                    yield {"type": "stage", "value": "out_of_scope"}
                    yield _assistant_scope_message_for_query(query, permission_ctx)
                    if request_id:
                        log_event(
                            "request_finished",
                            request_id,
                            route="decomposition_out_of_scope",
                            duration_ms=round((time.perf_counter() - started) * 1000, 2),
                        )
                    return
                yield "I could not retrieve data for this request. Please refine the question with class, subject, or timeframe."
                if request_id:
                    log_event("request_failed", request_id, reason="planner_empty")
                return
        except PlanValidationError as exc:
            if request_id:
                log_event("plan_invalid", request_id, error=str(exc))
        except Exception as exc:
            if request_id:
                if decomposition_mode:
                    log_event("batch_objective_planning_failed", request_id, reason=str(exc))
                log_event("planner_error", request_id, error=str(exc))

    # ── Step 3B: Legacy multi-objective handling (fallback) ──
    if not planner_succeeded and decomposition_mode and decision.get("type") != INTENT_OUT_OF_SCOPE:
        if len(objectives) > MAX_DECOMPOSE_OBJECTIVES:
            objectives = objectives[:MAX_DECOMPOSE_OBJECTIVES]
            if request_id:
                log_event(
                    "decomposition_truncated",
                    request_id,
                    max_objectives=MAX_DECOMPOSE_OBJECTIVES,
                    original_count=len(decision.get("objectives", [])),
                )

        yield {"type": "stage", "value": "decompose"}
        if request_id:
            log_event(
                "decomposition_started",
                request_id,
                objective_count=len(objectives),
                objectives=objectives,
            )

        if cached_sub_decisions is not None and len(cached_sub_decisions) == len(objectives):
            sub_decisions = cached_sub_decisions
        else:
            sub_decisions = [
                classify_and_generate_query(objective, permission_ctx, chat_history)
                for objective in objectives
            ]

        all_objectives_out_of_scope = bool(sub_decisions) and all(
            dec.get("type") == INTENT_OUT_OF_SCOPE for dec in sub_decisions
        )
        if all_objectives_out_of_scope:
            yield {"type": "stage", "value": "out_of_scope"}
            yield _assistant_scope_message_for_query(query, permission_ctx)
            if request_id:
                log_event(
                    "request_finished",
                    request_id,
                    route="decomposition_out_of_scope",
                    duration_ms=round((time.perf_counter() - started) * 1000, 2),
                )
            return

        yield {"type": "stage", "value": "multi_fetch"}
        subtask_jobs = [
            _run_objective_task(session, obj, sub_decisions[i], request_id, i + 1)
            for i, obj in enumerate(objectives)
        ]
        subtask_results = await asyncio.gather(*subtask_jobs)

        source_set = set()
        sections = []
        completed = 0
        for item in subtask_results:
            sections.append(item["section"])
            source_set.update(item.get("sources", []))
            if item.get("status") == "ok":
                completed += 1

        raw_data = "\n\n".join(sections)
        if source_set == {"database"}:
            data_source = "the school database"
        elif source_set == {"documents"}:
            data_source = "uploaded school documents"
        elif source_set:
            data_source = "the school database and uploaded documents"
        else:
            data_source = "no retrievable source"

        if request_id:
            log_event(
                "decomposition_finished",
                request_id,
                completed_subtasks=completed,
                total_subtasks=len(subtask_results),
                source_mix=sorted(source_set),
            )

        if completed == 0:
            yield "I could not retrieve data for the requested objectives. Please refine the question with class, subject, or timeframe."
            if request_id:
                log_event("request_failed", request_id, reason="decomposition_empty")
            return

    # ── Step 3C: Legacy single-step handling (fallback) ──
    if not planner_succeeded and not decomposition_mode and decision["type"] == "sql" and decision.get("sql"):
        yield {"type": "stage", "value": "sql_fetch"}
        rows = execute_sql_query(decision["sql"], session, request_id=request_id, subtask_id="sql-main")
        raw_data = json.dumps(rows, indent=2, default=str)
        data_source = "the school database"

    elif not planner_succeeded and not decomposition_mode and decision["type"] == "doc" and decision.get("search_phrase"):
        yield {"type": "stage", "value": "doc_fetch"}
        raw_data = search_documents(decision["search_phrase"], request_id=request_id, subtask_id="doc-main")
        data_source = "uploaded school documents"

    elif not planner_succeeded and not decomposition_mode and decision["type"] == "both":
        yield {"type": "stage", "value": "sql_fetch"}
        sql_rows, doc_chunks = "", ""
        vector_query = decision.get("search_phrase") or query
        rows: list[dict] = []

        if decision.get("sql"):
            rows = execute_sql_query(decision["sql"], session, request_id=request_id, subtask_id="sql-main")
            sql_rows = json.dumps(rows, indent=2, default=str)
            vector_query = _derive_vector_query_from_rows(
                rows,
                field=decision.get("vector_from_sql_field"),
                db_file_field=decision.get("db_file_field"),
                fallback=vector_query,
                prefix=decision.get("vector_prefix") or "",
            )

        if vector_query:
            yield {"type": "stage", "value": "doc_fetch"}
            doc_chunks = search_documents(vector_query, request_id=request_id, subtask_id="doc-main")

        if isinstance(rows, list) and rows and isinstance(rows[0], dict) and rows[0].get("error"):
            doc_chunks = "No assignment document details were retrieved due to SQL retrieval error."

        raw_data = f"--- Database ---\n{sql_rows}\n\n--- Documents ---\n{doc_chunks}"
        data_source = "the school database and uploaded documents"

    elif not planner_succeeded and not decomposition_mode and decision["type"] == INTENT_OUT_OF_SCOPE:
        yield {"type": "stage", "value": "out_of_scope"}
        message = decision.get("assistant_message") or (
            "I am your school assistant. "
            "Please ask about attendance, results, assignments, exams, announcements, or school documents."
        )
        if request_id:
            log_event("request_finished", request_id, route="out_of_scope", duration_ms=round((time.perf_counter() - started) * 1000, 2))
        yield message
        return

    elif not planner_succeeded:
        # If LLM couldn't decide, yield a simple message and stop
        if request_id:
            log_event("request_failed", request_id, reason="unclassified")
        yield "I couldn't understand your query. Please try rephrasing."
        return

    # ── Step 4: LLM formats the raw data into a nice response ──
    # final_response = format_response(role, query, raw_data, data_source)

    # return final_response

    # ── Step 4: Stream the formatted response token by token ──
    yield {"type": "stage", "value": "compose"}
    if skipped_objectives_notes:
        raw_data += "\n\n--- Skipped objectives (out of scope) ---\n" + "\n".join(skipped_objectives_notes)

    prompt = FORMAT_PROMPT.format(
        role=role,
        original_query=query,
        raw_data=raw_data,
        data_source=data_source,
        # In formatter.py — pass last 4 exchanges so LLM has context
        history_text="\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in chat_history[-4:]  # last 4 messages only (token budget)
        )
    )

    # .stream() yields tokens one by one as LLM generates them
    for token in streaming_llm.stream(prompt):
        yield token

    if request_id:
        log_event(
            "request_finished",
            request_id,
            route=decision.get("type"),
            source=data_source,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
