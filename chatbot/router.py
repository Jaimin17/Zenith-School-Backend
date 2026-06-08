import asyncio
import json
import uuid

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from deps import AllUser, UserRole
from schemas import (
    ChatRequest,
    ChatSessionCreateResponse,
    PaginatedChatSessionResponse,
    ChatSessionDetailResponse,
    SqlQueryRequest,
    SqlQueryResponse,
    VectorSearchRequest,
    VectorSearchResponse,
    SynthesizeRequest,
)
from chatbot.rag_engine import run_agent_stream, streaming_llm, _derive_vector_query_from_rows
from chatbot.classifier import classify_and_generate_query, classify_objectives_batch, INTENT_OUT_OF_SCOPE
from chatbot.intent_dispatcher import detect_entity_type, dispatch as dispatch_entity
from chatbot.sql_executor import execute_sql_query
from chatbot.vector_search import search_documents
from chatbot.formatter import FORMAT_PROMPT
from chatbot.permissions import get_user_permission_context
from chatbot.telemetry import create_request_id, log_event
from core.database import SessionDep
from repository.chatSession import (
    create_chat_session,
    list_user_chat_sessions,
    get_user_chat_session,
    append_chat_message,
    get_chat_session_detail,
)

router = APIRouter(
    prefix="/chatbot",
)


@router.post("/sessions", response_model=ChatSessionCreateResponse, status_code=201)
def create_session(current_user: AllUser, session: SessionDep):
    user, role = current_user
    created = create_chat_session(owner_id=user.id, owner_role=role, session=session)
    return ChatSessionCreateResponse(session_id=created.id, created_at=created.created_at)


@router.get("/sessions", response_model=PaginatedChatSessionResponse)
def list_sessions(current_user: AllUser, session: SessionDep, page: int = Query(1, ge=1)):
    user, role = current_user
    return list_user_chat_sessions(owner_id=user.id, owner_role=role, page=page, session=session)


@router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
def get_session(session_id: uuid.UUID, current_user: AllUser, session: SessionDep):
    user, role = current_user
    chat_session = get_user_chat_session(
        session_id=session_id,
        owner_id=user.id,
        owner_role=role,
        session=session,
    )
    if not chat_session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return get_chat_session_detail(chat_session=chat_session, session=session)


@router.post("/chat")
async def chat(request: ChatRequest, current_user: AllUser, session: SessionDep):
    """
    SSE endpoint — streams LLM response token by token.
    Frontend reads this as a stream, not a single response.
    """
    user, role = current_user
    request_id = create_request_id()
    chat_session = None

    if request.session_id:
        chat_session = get_user_chat_session(
            session_id=request.session_id,
            owner_id=user.id,
            owner_role=role,
            session=session,
        )
        if not chat_session:
            raise HTTPException(status_code=404, detail="Chat session not found")
    else:
        chat_session = create_chat_session(owner_id=user.id, owner_role=role, session=session)

    append_chat_message(
        chat_session=chat_session,
        role="user",
        content=request.query,
        session=session,
    )

    async def event_stream():
        assistant_chunks: list[str] = []
        try:
            # Send a start event so frontend knows stream began
            yield f"data: {json.dumps({'type': 'start', 'request_id': request_id, 'session_id': str(chat_session.id)})}\n\n"

            base_extra = {
                "first_name": getattr(user, "first_name", "") or "",
                "last_name": getattr(user, "last_name", "") or "",
                "display_name": " ".join(
                    part for part in [getattr(user, "first_name", ""), getattr(user, "last_name", "")] if part
                ).strip(),
                "selected_academic_year_id": str(request.selected_academic_year_id) if request.selected_academic_year_id else "",
            }

            if role == UserRole.PARENT:
                student_ids = {}
                for i, student in enumerate(user.students):
                    student_ids[i] = student.id

                extra_payload = {**base_extra, "student_ids": student_ids}

                # Stream tokens from the agent
                async for token in run_agent_stream(
                        query=request.query,
                        role=role,
                        user_id=user.id,
                        extra=extra_payload,
                        session=session,
                        chat_history=request.chat_history,
                        request_id=request_id,
                ):
                    payload: str
                    if isinstance(token, dict):
                        if token.get("type") == "token" and token.get("value"):
                            assistant_chunks.append(str(token.get("value")))
                        payload = json.dumps(token)
                    else:
                        assistant_chunks.append(str(token))
                        payload = json.dumps({"type": "token", "value": token})
                    yield f"data: {payload}\n\n"
                    await asyncio.sleep(0)  # yield control to event loop
            else:
                # Stream tokens from the agent
                async for token in run_agent_stream(
                        query=request.query,
                        role=role,
                        user_id=user.id,
                        extra=base_extra,
                        session=session,
                        chat_history=request.chat_history,
                        request_id=request_id,
                ):
                    payload: str
                    if isinstance(token, dict):
                        if token.get("type") == "token" and token.get("value"):
                            assistant_chunks.append(str(token.get("value")))
                        payload = json.dumps(token)
                    else:
                        assistant_chunks.append(str(token))
                        payload = json.dumps({"type": "token", "value": token})
                    yield f"data: {payload}\n\n"
                    await asyncio.sleep(0)  # yield control to event loop

            assistant_message = "".join(assistant_chunks).strip()
            if assistant_message:
                append_chat_message(
                    chat_session=chat_session,
                    role="assistant",
                    content=assistant_message,
                    session=session,
                )

            # Send done event so frontend knows stream ended
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            log_event("stream_error", request_id, error=str(e))
            error_payload = json.dumps({"type": "error", "message": str(e)})
            yield f"data: {error_payload}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # important for nginx deployments
            "Access-Control-Allow-Origin": "*",
        }
    )


# ─────────────────────────────────────────────────────────────────
# Shared helper — builds the extra context dict from current_user.
# Mirrors the same logic in /chat so all endpoints are consistent.
# ─────────────────────────────────────────────────────────────────
def _build_extra(user, role: str, selected_academic_year_id=None) -> dict:
    base = {
        "first_name": getattr(user, "first_name", "") or "",
        "last_name": getattr(user, "last_name", "") or "",
        "display_name": " ".join(
            p for p in [getattr(user, "first_name", ""), getattr(user, "last_name", "")] if p
        ).strip(),
        "selected_academic_year_id": str(selected_academic_year_id) if selected_academic_year_id else "",
    }
    if role == UserRole.PARENT:
        student_ids = {i: student.id for i, student in enumerate(user.students)}
        return {**base, "student_ids": student_ids}
    return base


# ─────────────────────────────────────────────────────────────────
# POST /chatbot/sql-query
# Classifies the query and executes SQL. Returns raw rows + any
# search phrases the orchestrator should pass to /vector-search.
# ─────────────────────────────────────────────────────────────────
@router.post("/sql-query", response_model=SqlQueryResponse)
def sql_query(request: SqlQueryRequest, current_user: AllUser, session: SessionDep):
    user, role = current_user
    extra = _build_extra(user, role, request.selected_academic_year_id)
    permission_ctx = get_user_permission_context(role, user.id, extra)

    # ── Step 1: Try existing repository APIs first ────────────────────
    entity_type = detect_entity_type(request.query)
    if entity_type:
        repo_rows = dispatch_entity(entity_type, user, role, session, extra)
        if repo_rows is not None:
            doc_needed = any(
                kw in request.query.lower()
                for kw in ["explain", "summary", "summarize", "details", "instructions", "rubric", "guide"]
            )
            return SqlQueryResponse(
                rows=repo_rows,
                data_source="the school database",
                query_type="both" if doc_needed else "sql",
                search_phrase=request.query if doc_needed else None,
                doc_search_phrases=[request.query] if doc_needed else [],
            )

    # ── Step 2: Fall back to LLM-generated SQL ────────────────────────
    decision = classify_and_generate_query(request.query, permission_ctx, request.chat_history)
    query_type = decision.get("type") or "sql"

    # Out-of-scope / greeting — return early with a friendly message
    if query_type == INTENT_OUT_OF_SCOPE:
        return SqlQueryResponse(
            rows=[],
            data_source="none",
            query_type=query_type,
            assistant_message=decision.get("assistant_message"),
        )

    rows: list[dict] = []
    sql: str | None = None
    search_phrase: str | None = decision.get("search_phrase")
    doc_search_phrases: list[str] = []

    # ── Decomposition mode: multiple independent objectives ────────
    if decision.get("decomposition_mode") and decision.get("objectives"):
        objective_items = decision.get("objective_items", [{"text": o} for o in decision["objectives"]])
        sub_decisions = classify_objectives_batch(
            query=request.query,
            objectives=objective_items,
            permission_ctx=permission_ctx,
            chat_history=request.chat_history,
        )
        for dec in sub_decisions:
            dec_type = dec.get("type", "")
            if dec_type in ("sql", "both") and dec.get("sql"):
                sub_rows = execute_sql_query(dec["sql"], session)
                rows.extend(sub_rows)
                # For "both": derive vector search phrase from SQL results
                if dec_type == "both":
                    derived = _derive_vector_query_from_rows(
                        sub_rows,
                        field=dec.get("vector_from_sql_field"),
                        db_file_field=dec.get("db_file_field"),
                        fallback=dec.get("search_phrase") or request.query,
                        prefix=dec.get("vector_prefix") or "",
                    )
                    doc_search_phrases.append(derived)
            if dec_type in ("doc", "both") and dec.get("search_phrase"):
                if dec.get("search_phrase") not in doc_search_phrases:
                    doc_search_phrases.append(dec["search_phrase"])
        return SqlQueryResponse(
            rows=rows,
            data_source="the school database",
            query_type="sql" if rows else ("doc" if doc_search_phrases else query_type),
            search_phrase=doc_search_phrases[0] if doc_search_phrases else None,
            doc_search_phrases=doc_search_phrases,
        )

    # ── Single-step SQL ────────────────────────────────────────────
    if query_type in ("sql", "both") and decision.get("sql"):
        sql = decision["sql"]
        rows = execute_sql_query(sql, session)
        if query_type == "both":
            search_phrase = _derive_vector_query_from_rows(
                rows,
                field=decision.get("vector_from_sql_field"),
                db_file_field=decision.get("db_file_field"),
                fallback=decision.get("search_phrase") or request.query,
                prefix=decision.get("vector_prefix") or "",
            )

    return SqlQueryResponse(
        rows=rows,
        sql=sql,
        data_source="the school database",
        query_type=query_type,
        search_phrase=search_phrase,
        doc_search_phrases=doc_search_phrases,
    )


# ─────────────────────────────────────────────────────────────────
# POST /chatbot/vector-search
# Direct ChromaDB search with an explicit search phrase.
# Auth is required; the search itself is not user-filtered.
# ─────────────────────────────────────────────────────────────────
@router.post("/vector-search", response_model=VectorSearchResponse)
def vector_search(request: VectorSearchRequest, current_user: AllUser):
    chunks = search_documents(request.search_phrase, k=request.k)
    return VectorSearchResponse(chunks=chunks, search_phrase=request.search_phrase)


# ─────────────────────────────────────────────────────────────────
# POST /chatbot/synthesize
# Streams an LLM-formatted response from pre-fetched raw_data.
# No classification or SQL — pure formatting + streaming.
# Optionally saves the exchange to a chat session.
# ─────────────────────────────────────────────────────────────────
@router.post("/synthesize")
async def synthesize(request: SynthesizeRequest, current_user: AllUser, session: SessionDep):
    user, role = current_user
    chat_session = None

    if request.session_id:
        chat_session = get_user_chat_session(
            session_id=request.session_id,
            owner_id=user.id,
            owner_role=role,
            session=session,
        )
        if not chat_session:
            raise HTTPException(status_code=404, detail="Chat session not found")
    else:
        chat_session = create_chat_session(owner_id=user.id, owner_role=role, session=session)

    append_chat_message(
        chat_session=chat_session,
        role="user",
        content=request.query,
        session=session,
    )

    async def event_stream():
        assistant_chunks: list[str] = []
        try:
            yield f"data: {json.dumps({'type': 'start', 'session_id': str(chat_session.id)})}\n\n"

            history_text = "\n".join(
                f"{m['role'].upper()}: {m['content']}"
                for m in request.chat_history[-4:]
            )
            prompt = FORMAT_PROMPT.format(
                role=role,
                original_query=request.query,
                raw_data=request.raw_data,
                data_source=request.data_source,
                history_text=history_text,
            )

            for token in streaming_llm.stream(prompt):
                assistant_chunks.append(str(token))
                payload = json.dumps({"type": "token", "value": str(token)})
                yield f"data: {payload}\n\n"
                await asyncio.sleep(0)

            assistant_message = "".join(assistant_chunks).strip()
            if assistant_message:
                append_chat_message(
                    chat_session=chat_session,
                    role="assistant",
                    content=assistant_message,
                    session=session,
                )

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            error_payload = json.dumps({"type": "error", "message": str(e)})
            yield f"data: {error_payload}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        }
    )


# ─────────────────────────────────────────────────────────────────
# POST /chatbot/orchestrated-chat
# Single endpoint that handles the full pipeline:
#   1. Intent dispatcher (existing repo APIs — no LLM)
#   2. LLM-SQL fallback (when no repo API matched)
#   3. Parallel ChromaDB vector searches
#   4. LLM synthesis → SSE stream
# The Next.js route is a thin JWT proxy that forwards here directly.
# ─────────────────────────────────────────────────────────────────
@router.post("/orchestrated-chat")
async def orchestrated_chat(request: ChatRequest, current_user: AllUser, session: SessionDep):
    user, role = current_user
    extra = _build_extra(user, role, request.selected_academic_year_id)
    permission_ctx = get_user_permission_context(role, user.id, extra)

    rows: list[dict] = []
    doc_search_phrases: list[str] = []
    quick_reply: str | None = None  # set for out-of-scope queries

    # ── Step 1: Try existing repository APIs ─────────────────────
    entity_type = detect_entity_type(request.query)
    if entity_type:
        repo_rows = dispatch_entity(entity_type, user, role, session, extra)
        if repo_rows is not None:
            rows = repo_rows
            doc_needed = any(
                kw in request.query.lower()
                for kw in ["explain", "summary", "summarize", "details", "instructions", "rubric", "guide"]
            )
            if doc_needed:
                doc_search_phrases = [request.query]

    # ── Step 2: LLM-SQL fallback (only when dispatcher had no match) ─
    if not rows and not doc_search_phrases and quick_reply is None:
        decision = classify_and_generate_query(request.query, permission_ctx, request.chat_history)
        query_type = decision.get("type") or "sql"

        if query_type == INTENT_OUT_OF_SCOPE:
            quick_reply = decision.get("assistant_message") or "I can only help with school-related questions."

        elif decision.get("decomposition_mode") and decision.get("objectives"):
            objective_items = decision.get("objective_items", [{"text": o} for o in decision["objectives"]])
            sub_decisions = classify_objectives_batch(
                query=request.query,
                objectives=objective_items,
                permission_ctx=permission_ctx,
                chat_history=request.chat_history,
            )
            for dec in sub_decisions:
                dec_type = dec.get("type", "")
                if dec_type in ("sql", "both") and dec.get("sql"):
                    sub_rows = execute_sql_query(dec["sql"], session)
                    rows.extend(sub_rows)
                    if dec_type == "both":
                        derived = _derive_vector_query_from_rows(
                            sub_rows,
                            field=dec.get("vector_from_sql_field"),
                            db_file_field=dec.get("db_file_field"),
                            fallback=dec.get("search_phrase") or request.query,
                            prefix=dec.get("vector_prefix") or "",
                        )
                        if derived not in doc_search_phrases:
                            doc_search_phrases.append(derived)
                if dec_type in ("doc", "both") and dec.get("search_phrase"):
                    sp = dec["search_phrase"]
                    if sp not in doc_search_phrases:
                        doc_search_phrases.append(sp)

        else:
            if query_type in ("sql", "both") and decision.get("sql"):
                rows = execute_sql_query(decision["sql"], session)
                if query_type == "both":
                    sp = _derive_vector_query_from_rows(
                        rows,
                        field=decision.get("vector_from_sql_field"),
                        db_file_field=decision.get("db_file_field"),
                        fallback=decision.get("search_phrase") or request.query,
                        prefix=decision.get("vector_prefix") or "",
                    )
                    doc_search_phrases = [sp]
            elif query_type == "doc" and decision.get("search_phrase"):
                doc_search_phrases = [decision["search_phrase"]]

    # ── Step 3: Parallel ChromaDB vector searches ─────────────────
    doc_chunks = ""
    if doc_search_phrases:
        chunk_results = await asyncio.gather(
            *[asyncio.to_thread(search_documents, sp) for sp in doc_search_phrases],
            return_exceptions=True,
        )
        doc_chunks = "\n\n".join(
            c for c in chunk_results
            if isinstance(c, str) and not c.startswith("No relevant")
        )

    # ── Step 4: Build combined context string ─────────────────────
    # Strip error sentinel rows produced by execute_sql_query on failure
    rows = [r for r in rows if "error" not in r]
    has_rows = bool(rows)
    has_docs = bool(doc_chunks)
    if has_rows and has_docs:
        raw_data = f"--- Database ---\n{json.dumps(rows, indent=2)}\n\n--- Documents ---\n{doc_chunks}"
        data_source = "the school database and uploaded documents"
    elif has_docs:
        raw_data = doc_chunks
        data_source = "uploaded school documents"
    elif has_rows:
        raw_data = json.dumps(rows, indent=2)
        data_source = "the school database"
    else:
        raw_data = ""
        data_source = "the school database"

    # ── Step 5: Set up chat session ───────────────────────────────
    chat_session = None
    if request.session_id:
        chat_session = get_user_chat_session(
            session_id=request.session_id,
            owner_id=user.id,
            owner_role=role,
            session=session,
        )
    if not chat_session:
        chat_session = create_chat_session(owner_id=user.id, owner_role=role, session=session)

    append_chat_message(chat_session=chat_session, role="user", content=request.query, session=session)

    # ── Step 6: SSE stream ────────────────────────────────────────
    async def event_stream():
        assistant_chunks: list[str] = []
        try:
            yield f"data: {json.dumps({'type': 'start', 'session_id': str(chat_session.id)})}\n\n"

            if quick_reply:
                yield f"data: {json.dumps({'type': 'token', 'value': quick_reply})}\n\n"
                assistant_chunks.append(quick_reply)
            else:
                history_text = "\n".join(
                    f"{m['role'].upper()}: {m['content']}"
                    for m in request.chat_history[-4:]
                )
                prompt = FORMAT_PROMPT.format(
                    role=role,
                    original_query=request.query,
                    raw_data=raw_data or "No data found for this query.",
                    data_source=data_source,
                    history_text=history_text,
                )
                for token in streaming_llm.stream(prompt):
                    assistant_chunks.append(str(token))
                    yield f"data: {json.dumps({'type': 'token', 'value': str(token)})}\n\n"
                    await asyncio.sleep(0)

            assistant_message = "".join(assistant_chunks).strip()
            if assistant_message:
                append_chat_message(
                    chat_session=chat_session,
                    role="assistant",
                    content=assistant_message,
                    session=session,
                )

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        }
    )
