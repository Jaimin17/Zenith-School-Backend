from sqlmodel import Session
import asyncio

from chatbot.permissions import get_user_permission_context
from chatbot.classifier import classify_and_generate_query, INTENT_OUT_OF_SCOPE
from chatbot.sql_executor import execute_sql_query
from chatbot.vector_search import search_documents
from chatbot.formatter import FORMAT_PROMPT
from langchain_ollama import OllamaLLM
import uuid, json
from typing import AsyncGenerator, Any
import time

from core.config import settings
from chatbot.telemetry import log_event

# Separate LLM instance for streaming (formatter step only)
streaming_llm = OllamaLLM(model=settings.CHATBOT_MODEL, temperature=0.3, streaming=True)
MAX_DECOMPOSE_OBJECTIVES = 4


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

    # ── Step 3A: Multi-objective handling (decomposition mode) ──
    objectives = decision.get("objectives", [])
    decomposition_mode = bool(decision.get("decomposition_mode")) and len(objectives) > 1
    if decomposition_mode and decision.get("type") != INTENT_OUT_OF_SCOPE:
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

        sub_decisions: list[dict[str, Any]] = []
        for objective in objectives:
            sub_decisions.append(classify_and_generate_query(objective, permission_ctx, chat_history))

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

    # ── Step 3: Execute based on LLM decision ──
    if not decomposition_mode and decision["type"] == "sql" and decision.get("sql"):
        yield {"type": "stage", "value": "sql_fetch"}
        rows = execute_sql_query(decision["sql"], session, request_id=request_id, subtask_id="sql-main")
        raw_data = json.dumps(rows, indent=2, default=str)
        data_source = "the school database"

    elif not decomposition_mode and decision["type"] == "doc" and decision.get("search_phrase"):
        yield {"type": "stage", "value": "doc_fetch"}
        raw_data = search_documents(decision["search_phrase"], request_id=request_id, subtask_id="doc-main")
        data_source = "uploaded school documents"

    elif not decomposition_mode and decision["type"] == "both":
        yield {"type": "stage", "value": "sql_fetch"}
        sql_rows, doc_chunks = "", ""

        if decision.get("sql"):
            rows = execute_sql_query(decision["sql"], session, request_id=request_id, subtask_id="sql-main")
            sql_rows = json.dumps(rows, indent=2, default=str)

        if decision.get("search_phrase"):
            yield {"type": "stage", "value": "doc_fetch"}
            doc_chunks = search_documents(decision["search_phrase"], request_id=request_id, subtask_id="doc-main")

        raw_data = f"--- Database ---\n{sql_rows}\n\n--- Documents ---\n{doc_chunks}"
        data_source = "the school database and uploaded documents"

    elif not decomposition_mode and decision["type"] == INTENT_OUT_OF_SCOPE:
        yield {"type": "stage", "value": "out_of_scope"}
        message = (
            "I can help with school data and documents such as assignments, attendance, results, "
            "schedule, announcements, events, and policies. "
            "Try asking: 'Show my latest assignments' or 'Summarize this month's attendance.'"
        )
        if request_id:
            log_event("request_finished", request_id, route="out_of_scope", duration_ms=round((time.perf_counter() - started) * 1000, 2))
        yield message
        return

    else:
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
