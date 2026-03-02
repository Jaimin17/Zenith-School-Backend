from sqlmodel import Session

from chatbot.permissions import get_user_permission_context
from chatbot.classifier import classify_and_generate_query
from chatbot.sql_executor import execute_sql_query
from chatbot.vector_search import search_documents
from chatbot.formatter import format_response, FORMAT_PROMPT
from langchain_ollama import OllamaLLM
import uuid, json
from typing import AsyncGenerator

# Separate LLM instance for streaming (formatter step only)
streaming_llm = OllamaLLM(model="tinyllama", temperature=0.3, streaming=True)


async def run_agent_stream(session: Session, query: str, role: str, user_id: uuid.UUID, extra: dict = {},
                           chat_history: list[dict] = []) -> \
        AsyncGenerator[str, None]:
    """
    Full agent pipeline with streaming on the final formatting step.
    Steps 1-3 run normally (classify, fetch data).
    Step 4 (formatter) streams token by token.
    """

    # ── Step 1: Build permission context ──
    permission_ctx = get_user_permission_context(role, user_id, extra)

    # ── Step 2: LLM classifies query and generates SQL or search phrase ──
    # This step does NOT stream — we need the full decision before proceeding
    decision = classify_and_generate_query(query, permission_ctx, chat_history)

    print(f"🧠 LLM Decision: {decision['reasoning']}")  # helpful for debugging

    raw_data = ""
    data_source = ""

    # ── Step 3: Execute based on LLM decision ──
    if decision["type"] == "sql" and decision.get("sql"):
        rows = execute_sql_query(decision["sql"], session)
        raw_data = json.dumps(rows, indent=2, default=str)
        data_source = "the school database"

    elif decision["type"] == "doc" and decision.get("search_phrase"):
        raw_data = search_documents(decision["search_phrase"])
        data_source = "uploaded school documents"

    elif decision["type"] == "both":
        sql_rows, doc_chunks = "", ""

        if decision.get("sql"):
            rows = execute_sql_query(decision["sql"], session)
            sql_rows = json.dumps(rows, indent=2, default=str)

        if decision.get("search_phrase"):
            doc_chunks = search_documents(decision["search_phrase"])

        raw_data = f"--- Database ---\n{sql_rows}\n\n--- Documents ---\n{doc_chunks}"
        data_source = "the school database and uploaded documents"

    else:
        # If LLM couldn't decide, yield a simple message and stop
        yield "I couldn't understand your query. Please try rephrasing."
        return

    # ── Step 4: LLM formats the raw data into a nice response ──
    # final_response = format_response(role, query, raw_data, data_source)

    # return final_response

    # ── Step 4: Stream the formatted response token by token ──
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
