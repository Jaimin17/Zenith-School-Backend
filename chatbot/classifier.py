from langchain_core.prompts import PromptTemplate
from chatbot.schema_reference import (
    DB_SCHEMA_COMPACT,
)
import re
import json
from typing import Any

from chatbot.llm_factory import create_llm

llm = create_llm(temperature=0)

# Intent constants used by orchestrator and telemetry.
INTENT_SCHOOL_DATA = "sql"
INTENT_SCHOOL_DOCS = "doc"
INTENT_HYBRID = "both"
INTENT_OUT_OF_SCOPE = "out_of_scope"

_MULTI_OBJECTIVE_JOINERS = re.compile(r"\b(and|also|plus|along with|as well as|compare)\b", re.IGNORECASE)
_DOC_INTENT_HINTS = {
    "summary", "summarize", "details", "detail", "explain", "describe",
    "pdf", "document", "instructions", "guidelines", "rubric",
}

# ─────────────────────────────────────────────────────────────────
# PROMPT 1: TYPE DECIDER  (~200 tokens)
# Tiny prompt, one job: return sql / doc / both
# ─────────────────────────────────────────────────────────────────
TYPE_DECIDER_PROMPT = PromptTemplate(
    input_variables=["query", "chat_history"],
    template="""\
    You are a routing classifier for a school assistant pipeline.
    Reply with ONE word only: sql, doc, both, or out_of_scope.

    Pipeline overview:
    - sql: Query structured school DB data (attendance, results, exams, assignments, announcements, events).
    - doc: Query uploaded documents (instructions, rubric, policy, handbook, syllabus).
    - both: Use SQL first to identify the exact target, then use docs for explanation/summary/details.
    - out_of_scope: Greeting/small talk/non-school topics.

    Decision rules:
    - Choose both when user asks summary/details/explanation of a latest/specific announcement or assignment.
    - Choose both when exact document target must be identified from DB first (latest, recent, current, specific subject).
    - Choose doc only when the user directly asks for document content and target is already explicit.
    - Choose sql only when answer is purely structured data and does not require document explanation.

    Examples:
    - "Show my attendance this month" -> sql
    - "Open assignment rubric for Algebra Unit 3" -> doc
    - "Give me summary of latest math assignment" -> both
    - "Hello" -> out_of_scope
    
    previous history: {chat_history}
    
    Query: {query}
    
    One word:""",
)


BATCH_OBJECTIVE_PLANNER_PROMPT = PromptTemplate(
        input_variables=[
                "query",
                "objectives_json",
        "objective_metadata_json",
                "mandatory_filter",
                "allowed",
                "schema",
                "chat_history",
        ],
        template="""\
        You are planning objective-level retrieval for a school assistant.

        Return JSON ONLY. No markdown. No explanation.

        Input query: {query}
        Objectives (JSON array): {objectives_json}
        Objective metadata (JSON array): {objective_metadata_json}
        previous history: {chat_history}

        MANDATORY SQL FILTER (must be included in every SQL when SQL is used):
        {mandatory_filter}

        SQL safety rules:
        - Only SELECT.
        - No INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE/CREATE.
        - Every table needs is_delete=false.
        - Use only these tables: {allowed}
        - Prefer ILIKE '%term%' for text matching.

        Schema reference:
        {schema}

        Output format:
        [
            {{
                "objective": "<objective text>",
                "type": "sql|doc|both|out_of_scope",
                "sql": "<SELECT SQL or null>",
                "search_phrase": "<document query phrase or null>",
                "vector_from_sql_field": "<optional field name from SQL rows for dependent vector query>",
                "db_file_field": "<optional database file-name field like pdf_name>",
                "vector_prefix": "<optional prefix text for vector query>",
                "reasoning": "<short reason>"
            }}
        ]

        Dependency hint:
        - If objective needs SQL result first (example: latest assignment title, then fetch assignment details from docs),
                        set type='both', provide sql, and set vector_from_sql_field to the SQL column name to use.
                - If objective metadata says needs_docs=true, prefer type='both' (or 'doc' when SQL is unnecessary).
        """,
)


OBJECTIVE_EXTRACTOR_PROMPT = PromptTemplate(
        input_variables=["query", "chat_history"],
        template="""\
        You are extracting retrieval objectives for a school assistant.

        Return JSON only (no markdown):
        [
            {{
                "text": "objective text",
                "needs_docs": true,
                "preferred_source": "sql|doc|both",
                "dependency_hint": "sql_then_vector|independent"
            }}
        ]

        Rules:
        - Max 4 objectives.
        - Keep each objective short and actionable.
        - If user asks summary/details for assignment/exam/policy, set needs_docs=true.
        - If objective needs latest/filtered database record then document expansion, use dependency_hint='sql_then_vector'.

        previous history: {chat_history}
        Query: {query}
        """,
)

# ─────────────────────────────────────────────────────────────────
# PROMPT 2: SQL GENERATOR  (~700 tokens)
#
# KEY FIX 1: mandatory_filter at the TOP (LLM reads start first)
# KEY FIX 2: ILIKE rule explicitly stated with examples
# ─────────────────────────────────────────────────────────────────
SQL_GENERATOR_PROMPT = PromptTemplate(
    input_variables=["mandatory_filter", "schema", "allowed", "query", "chat_history"],
    template="""\
    MANDATORY — your SQL MUST include this exact WHERE condition:
    {mandatory_filter}
    
    Task: Write a PostgreSQL SELECT query for a school system.
    
    previous history: {chat_history}
    
    Rules:
    - Only SELECT. No INSERT/UPDATE/DELETE/DROP.
    - Every table needs AND is_delete=false.
    - Always quote: "class".
    - Only use these tables: {allowed}
    - Use templates from schema when available.
    - NEVER use = for text columns (name, title, etc). ALWAYS use ILIKE '%keyword%'.
      Example: user says "math" → s.name ILIKE '%math%' (matches Mathematics, Math 101, etc)
      Example: user says "sci" → s.name ILIKE '%sci%' (matches Science, Computer Science)
      Apply ILIKE to: subject.name, exam.title, assignment.title, class.name, event.title, announcement.title.
    
    {schema}
    
    Question: {query}
    
    Write ONLY the SQL. No explanation. No markdown. Start with SELECT:""",
)

# ─────────────────────────────────────────────────────────────────
# POST-PROCESSING: enforce ILIKE as a Python safety net
#
# Even if the LLM ignores the prompt rule and generates:
#   LOWER(s.name) = LOWER('math')   or   s.name = 'math'
# this function converts them to:
#   s.name ILIKE '%math%'
#
# Patterns caught:
#   1. LOWER(col) = LOWER('val')
#   2. col = 'val'  (on known text columns only)
# ─────────────────────────────────────────────────────────────────

# Text columns where fuzzy matching should always apply
_FUZZY_COLUMNS = {
    "s.name", "subject.name",
    "e.title", "exam.title",
    "a.title", "assignment.title",
    "c.name", "class.name",
    "ev.title", "event.title",
    "an.title", "announcement.title",
    "l.name", "lesson.name",
    "t.first_name", "t.last_name",
    "teacher.first_name", "teacher.last_name",
}


def _enforce_ilike(sql: str) -> str:
    """
    Post-process LLM-generated SQL to replace exact string matches
    on text columns with ILIKE fuzzy matches.

    Converts:
      LOWER(s.name) = LOWER('math')  →  s.name ILIKE '%math%'
      s.name = 'Mathematics'         →  s.name ILIKE '%Mathematics%'
    """

    # Pattern 1: LOWER(col) = LOWER('value')  or  LOWER(col) = LOWER("value")
    pattern1 = re.compile(
        r"LOWER\(\s*([a-zA-Z_.]+)\s*\)\s*=\s*LOWER\(\s*['\"]([^'\"]+)['\"]\s*\)",
        re.IGNORECASE,
    )

    def replace_lower_lower(m: re.Match) -> str:
        col, val = m.group(1), m.group(2)
        print(f"🔧 Fixed LOWER()=LOWER(): {m.group(0)} → {col} ILIKE '%{val}%'")
        return f"{col} ILIKE '%{val}%'"

    sql = pattern1.sub(replace_lower_lower, sql)

    # Pattern 2: col = 'value'  — only on known fuzzy columns
    pattern2 = re.compile(
        r"([a-zA-Z_.]+)\s*=\s*['\"]([^'\"]+)['\"]",
        re.IGNORECASE,
    )

    def replace_exact_eq(m: re.Match) -> str:
        col, val = m.group(1).strip(), m.group(2)
        if col.lower() in {c.lower() for c in _FUZZY_COLUMNS}:
            print(f"🔧 Fixed exact match: {m.group(0)} → {col} ILIKE '%{val}%'")
            return f"{col} ILIKE '%{val}%'"
        return m.group(0)  # leave non-text columns (UUIDs, booleans) untouched

    sql = pattern2.sub(replace_exact_eq, sql)

    return sql


# ─────────────────────────────────────────────────────────────────
# MANDATORY FILTERS per role
# Injected as the FIRST thing LLM reads so it cannot be ignored
# ─────────────────────────────────────────────────────────────────
def _build_mandatory_filter(role: str, user_id: str, extra: dict) -> str:
    if role == "student":
        return (
            f"For attendance/result tables: WHERE student_id = CAST('{user_id}' AS UUID)\n"
            f"For schedule: filter via student.id = CAST('{user_id}' AS UUID)\n"
            f"For announcements/events: WHERE (class_id = (SELECT class_id FROM student WHERE id = CAST('{user_id}' AS UUID)) OR class_id IS NULL)"
        )

    if role == "teacher":
        return (
            f"For lessons: WHERE lesson.teacher_id = CAST('{user_id}' AS UUID)\n"
            f"For student data: only students in classes taught by this teacher\n"
            f"For announcements: WHERE class_id IN (SELECT class_id FROM lesson WHERE teacher_id = CAST('{user_id}' AS UUID))"
        )

    if role == "parent":
        child_id = _resolve_parent_child_id(extra)
        if child_id:
            return (
                f"Child's student_id = CAST('{child_id}' AS UUID)\n"
                f"For attendance/result: WHERE student_id = CAST('{child_id}' AS UUID)\n"
                f"For announcements: WHERE (class_id = (SELECT class_id FROM student WHERE id = CAST('{child_id}' AS UUID)) OR class_id IS NULL)"
            )
        return (
            f"Get child first: SELECT id FROM student WHERE parent_id = CAST('{user_id}' AS UUID) AND is_delete=false\n"
            f"Then filter all student data by that child's id"
        )

    # admin
    return "No mandatory filter. Show all relevant data unless query specifies a person/class."


def _looks_like_greeting(query: str) -> bool:
    return bool(
        re.match(
            r"^\s*(hi|hello|hey|hii|hlo|good\s+morning|good\s+afternoon|good\s+evening)\b",
            query.strip(),
            re.IGNORECASE,
        )
    )


def _extract_user_name(permission_ctx: dict) -> str | None:
    extra = permission_ctx.get("extra", {}) if isinstance(permission_ctx, dict) else {}
    if not isinstance(extra, dict):
        return None

    display = str(extra.get("display_name", "")).strip()
    if display:
        return display

    first = str(extra.get("first_name", "")).strip()
    last = str(extra.get("last_name", "")).strip()
    full = f"{first} {last}".strip()
    return full or None


def _assistant_scope_message_for_query(query: str, permission_ctx: dict) -> str:
    name = _extract_user_name(permission_ctx)
    if _looks_like_greeting(query):
        if name:
            return (
                f"Hi {name}! I am your school assistant. "
                "Ask me about attendance, results, assignments, exams, announcements, or school documents."
            )
        return (
            "Hi! I am your school assistant. "
            "Ask me about attendance, results, assignments, exams, announcements, or school documents."
        )

    if name:
        return (
            f"Sorry {name}, I can help with school-related questions only. "
            "Please ask about attendance, results, assignments, exams, announcements, or school documents."
        )

    return (
        "Sorry, I can help with school-related questions only. "
        "Please ask about attendance, results, assignments, exams, announcements, or school documents."
    )


def _decompose_query(query: str) -> list[str]:
    if not _MULTI_OBJECTIVE_JOINERS.search(query):
        return [query.strip()]
    parts = re.split(r"\b(?:and|also|plus|along with|as well as|compare)\b", query, flags=re.IGNORECASE)
    return [p.strip(" ,.") for p in parts if p.strip(" ,.")]


def _resolve_parent_child_id(extra: dict) -> str:
    if not isinstance(extra, dict):
        return ""

    child_id = str(extra.get("child_id", "")).strip()
    if child_id and child_id.lower() not in {"undefined", "null"}:
        return child_id

    student_ids = extra.get("student_ids")
    if isinstance(student_ids, dict):
        for val in student_ids.values():
            sid = str(val).strip()
            if sid and sid.lower() not in {"undefined", "null"}:
                return sid

    return ""


def _derive_single_objective_type(objective_item: dict[str, Any], query: str) -> str | None:
    preferred_source = str(objective_item.get("preferred_source", "")).strip().lower()
    dependency_hint = str(objective_item.get("dependency_hint", "")).strip().lower()
    needs_docs = bool(objective_item.get("needs_docs", False))

    if dependency_hint == "sql_then_vector":
        return "both"

    if preferred_source == "both":
        return "both"

    if preferred_source == "sql" and needs_docs:
        return "both"

    if preferred_source in {"sql", "doc"}:
        return preferred_source

    if needs_docs or _requires_sql_then_docs([objective_item], query):
        return "both"

    return None


def _requires_sql_then_docs(objective_items: list[dict[str, Any]], query: str) -> bool:
    q = query.lower()
    query_has_latest_hint = any(word in q for word in {"latest", "recent", "last", "current"})
    query_wants_explanation = any(word in q for word in {"summary", "summarize", "details", "detail", "explain"})

    for item in objective_items:
        if str(item.get("dependency_hint", "")).strip().lower() == "sql_then_vector":
            return True
        if str(item.get("preferred_source", "")).strip().lower() == "both":
            return True

    return query_has_latest_hint and query_wants_explanation


def _default_file_field_for_objective(objective: str) -> str | None:
    objective_l = objective.lower()
    if "assignment" in objective_l:
        return "pdf_name"
    if any(word in objective_l for word in {"announcement", "notice", "circular"}):
        return "attachment"
    return None


def _extract_objectives_via_llm(query: str, chat_history: list[dict]) -> list[dict[str, Any]]:
    raw = llm.invoke(OBJECTIVE_EXTRACTOR_PROMPT.format(
        query=query,
        chat_history="\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in chat_history[-4:]
        ),
    )).strip()

    cleaned = re.sub(r"```(?:json)?\s*", "", raw, flags=re.IGNORECASE).replace("```", "").strip()
    parsed = None
    try:
        parsed = json.loads(cleaned)
    except Exception:
        match = re.search(r"(\[.*\]|\{.*\})", cleaned, flags=re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(1))
            except Exception:
                parsed = None

    items = parsed if isinstance(parsed, list) else []
    normalized: list[dict[str, Any]] = []
    for item in items[:4]:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        preferred_source = str(item.get("preferred_source", "sql")).strip().lower()
        if preferred_source not in {"sql", "doc", "both"}:
            preferred_source = "sql"

        normalized.append({
            "text": text,
            "needs_docs": bool(item.get("needs_docs", False)),
            "preferred_source": preferred_source,
            "dependency_hint": str(item.get("dependency_hint", "independent")).strip().lower(),
            "db_file_field": _default_file_field_for_objective(text),
        })

    return normalized


def _build_objective_items(query: str, chat_history: list[dict]) -> list[dict[str, Any]]:
    llm_items = _extract_objectives_via_llm(query, chat_history)
    if llm_items:
        return llm_items[:4]

    fallback = _decompose_query(query)[:4]
    query_words = set(re.findall(r"\b\w+\b", query.lower()))
    query_needs_docs = bool(query_words.intersection(_DOC_INTENT_HINTS))
    items: list[dict[str, Any]] = []
    for obj in fallback:
        obj_words = set(re.findall(r"\b\w+\b", obj.lower()))
        needs_docs = query_needs_docs or bool(obj_words.intersection(_DOC_INTENT_HINTS))
        items.append({
            "text": obj,
            "needs_docs": needs_docs,
            "preferred_source": "both" if needs_docs else "sql",
            "dependency_hint": "sql_then_vector" if needs_docs else "independent",
            "db_file_field": _default_file_field_for_objective(obj),
        })
    return items


# ─────────────────────────────────────────────────────────────────
# STEP 1: Decide type
# ─────────────────────────────────────────────────────────────────
def _decide_type(query: str, chat_history: list[dict]) -> str:
    raw = llm.invoke(TYPE_DECIDER_PROMPT.format(
        query=query,
        chat_history="\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in chat_history[-4:]  # last 4 messages only (token budget)
        ))).strip().lower()
    first = raw.split()[0] if raw.split() else INTENT_OUT_OF_SCOPE
    result = first if first in {"sql", "doc", "both", INTENT_OUT_OF_SCOPE} else INTENT_OUT_OF_SCOPE
    print(f"🤖 LLM type router → '{result}' (raw='{raw}')")
    return result


def _validate_sql_for_role(sql: str, role: str, user_id: str, extra: dict) -> bool:
    """Hard enforcement — LLM output must contain the right WHERE clause."""
    if role == "student":
        return user_id.lower() in sql.lower()
    if role == "parent":
        child_id = _resolve_parent_child_id(extra)
        return child_id.lower() in sql.lower() if child_id else True
    if role == "teacher":
        return user_id.lower() in sql.lower()
    return True  # admin: no restriction


# ─────────────────────────────────────────────────────────────────
# STEP 2: Generate SQL
# ─────────────────────────────────────────────────────────────────
def _generate_sql(query: str, permission_ctx: dict, chat_history: list[dict]) -> str | None:
    role = permission_ctx["role"]
    user_id = permission_ctx["user_id"]
    extra = permission_ctx.get("extra", {})

    mandatory_filter = _build_mandatory_filter(role, user_id, extra)

    prompt = SQL_GENERATOR_PROMPT.format(
        mandatory_filter=mandatory_filter,
        schema=DB_SCHEMA_COMPACT,
        allowed=", ".join(permission_ctx["allowed_tables"]),
        query=query,
        chat_history="\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in chat_history[-4:]  # last 4 messages only (token budget)
        )
    )

    raw = llm.invoke(prompt).strip()

    # Strip markdown fences if LLM added them
    raw = re.sub(r"```(?:sql|postgresql)?\s*", "", raw, flags=re.IGNORECASE)
    raw = raw.replace("```", "").strip()

    # Must start with SELECT
    if not raw.upper().lstrip().startswith("SELECT"):
        print(f"⚠️ SQL generator bad output: '{raw[:120]}'")
        return None

    # Block dangerous mutation keywords
    danger = re.search(
        r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE)\b", raw, re.IGNORECASE
    )
    if danger:  
        print(f"🚫 Blocked dangerous keyword: {danger.group()}")
        return None

    # Python-level safety net: fix LOWER()= or exact = to ILIKE
    raw = _enforce_ilike(raw)

    if not _validate_sql_for_role(raw, role, user_id, extra):
        print("🚫 Security: mandatory filter missing from generated SQL")
        return None

    print(f"📝 SQL:\n{raw}\n")
    return raw


# ─────────────────────────────────────────────────────────────────
# PUBLIC API — called by rag_engine.py
# ─────────────────────────────────────────────────────────────────
def classify_and_generate_query(query: str, permission_ctx: dict, chat_history: list[dict]) -> dict:
    """
    Step 1: decide type (sql / doc / both)
    Step 2: generate SQL with ILIKE fuzzy matching enforced

    Returns:
        { type, sql, search_phrase, reasoning }
    """
    objective_items = _build_objective_items(query, chat_history)
    objectives = [item["text"] for item in objective_items]
    decomposition_mode = len(objectives) > 1

    if decomposition_mode:
        return {
            "type": None,
            "sql": None,
            "search_phrase": None,
            "reasoning": "type=decomposition_pending | sql=no | doc=no",
            "decomposition_mode": decomposition_mode,
            "objectives": objectives,
            "objective_items": objective_items,
        }

    single_objective = objective_items[0] if objective_items else {}
    query_type = _derive_single_objective_type(single_objective, query)
    if not query_type:
        query_type = _decide_type(query, chat_history)

    if query_type == INTENT_OUT_OF_SCOPE:
        return {
            "type": INTENT_OUT_OF_SCOPE,
            "sql": None,
            "search_phrase": None,
            "assistant_message": _assistant_scope_message_for_query(query, permission_ctx),
            "reasoning": "type=out_of_scope | sql=no | doc=no",
            "decomposition_mode": decomposition_mode,
            "objectives": objectives,
            "objective_items": objective_items,
        }

    if _requires_sql_then_docs(objective_items, query):
        query_type = "both"

    if any(item.get("needs_docs") for item in objective_items) and query_type == "sql":
        query_type = "both"

    sql = None
    search_phrase = None

    if query_type in ("sql", "both"):
        sql = _generate_sql(query, permission_ctx, chat_history)
        if not sql:
            print("⚠️ SQL failed → falling back to doc")
            query_type = "doc"

    if query_type in ("doc", "both"):
        search_phrase = query

    vector_from_sql_field = None
    db_file_field = None
    if query_type == "both":
        db_file_field = next((item.get("db_file_field") for item in objective_items if item.get("db_file_field")), None)
        if db_file_field:
            vector_from_sql_field = db_file_field
        else:
            vector_from_sql_field = "title"

    return {
        "type": query_type,
        "sql": sql,
        "search_phrase": search_phrase,
        "vector_from_sql_field": vector_from_sql_field,
        "db_file_field": db_file_field,
        "vector_prefix": "",
        "reasoning": f"type={query_type} | sql={'yes' if sql else 'no'} | doc={'yes' if search_phrase else 'no'}",
        "decomposition_mode": decomposition_mode,
        "objectives": objectives,
        "objective_items": objective_items,
    }


def _normalize_sql_candidate(sql: str | None, permission_ctx: dict) -> str | None:
    if not sql:
        return None

    raw = str(sql).strip()
    raw = re.sub(r"```(?:sql|postgresql)?\s*", "", raw, flags=re.IGNORECASE)
    raw = raw.replace("```", "").strip()

    if not raw.upper().lstrip().startswith("SELECT"):
        return None

    if re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE)\b", raw, re.IGNORECASE):
        return None

    raw = _enforce_ilike(raw)

    role = permission_ctx["role"]
    user_id = permission_ctx["user_id"]
    extra = permission_ctx.get("extra", {})
    if not _validate_sql_for_role(raw, role, user_id, extra):
        return None

    return raw


def classify_objectives_batch(
        query: str,
        objectives: list[dict[str, Any]] | list[str],
        permission_ctx: dict,
        chat_history: list[dict],
) -> list[dict]:
    if not objectives:
        return []

    objective_items: list[dict[str, Any]] = []
    for item in objectives:
        if isinstance(item, dict):
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            objective_items.append({
                "text": text,
                "needs_docs": bool(item.get("needs_docs", False)),
                "preferred_source": str(item.get("preferred_source", "sql")).strip().lower(),
                "dependency_hint": str(item.get("dependency_hint", "independent")).strip().lower(),
                "db_file_field": item.get("db_file_field") or _default_file_field_for_objective(text),
            })
        else:
            text = str(item).strip()
            if not text:
                continue
            objective_items.append({
                "text": text,
                "needs_docs": False,
                "preferred_source": "sql",
                "dependency_hint": "independent",
                "db_file_field": _default_file_field_for_objective(text),
            })

    objective_texts = [item["text"] for item in objective_items]

    role = permission_ctx["role"]
    user_id = permission_ctx["user_id"]
    extra = permission_ctx.get("extra", {})
    mandatory_filter = _build_mandatory_filter(role, user_id, extra)

    raw = llm.invoke(BATCH_OBJECTIVE_PLANNER_PROMPT.format(
        query=query,
        objectives_json=json.dumps(objective_texts, ensure_ascii=True),
        objective_metadata_json=json.dumps(objective_items, ensure_ascii=True),
        mandatory_filter=mandatory_filter,
        allowed=", ".join(permission_ctx["allowed_tables"]),
        schema=DB_SCHEMA_COMPACT,
        chat_history="\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in chat_history[-4:]
        ),
    )).strip()

    cleaned = re.sub(r"```(?:json)?\s*", "", raw, flags=re.IGNORECASE).replace("```", "").strip()
    parsed = None
    try:
        parsed = json.loads(cleaned)
    except Exception:
        match = re.search(r"(\[.*\]|\{.*\})", cleaned, flags=re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(1))
            except Exception:
                parsed = None

    if isinstance(parsed, dict):
        items = parsed.get("objectives") if isinstance(parsed.get("objectives"), list) else []
    elif isinstance(parsed, list):
        items = parsed
    else:
        items = []

    normalized: list[dict] = []
    for i, objective in enumerate(objective_texts):
        item = items[i] if i < len(items) and isinstance(items[i], dict) else {}
        objective_meta = objective_items[i] if i < len(objective_items) else {}
        decision_type = str(item.get("type", "doc")).strip().lower()
        if decision_type not in {"sql", "doc", "both", INTENT_OUT_OF_SCOPE}:
            decision_type = "doc"

        sql = _normalize_sql_candidate(item.get("sql"), permission_ctx)
        search_phrase = item.get("search_phrase") or objective

        if decision_type in {"sql", "both"} and not sql:
            decision_type = "doc"

        if objective_meta.get("needs_docs") and decision_type == "sql":
            decision_type = "both"

        vector_from_sql_field = item.get("vector_from_sql_field")
        db_file_field = item.get("db_file_field") or objective_meta.get("db_file_field")
        if decision_type != "both":
            vector_from_sql_field = None
        elif not vector_from_sql_field:
            vector_from_sql_field = db_file_field or "title"

        normalized.append({
            "objective": objective,
            "type": decision_type,
            "sql": sql,
            "search_phrase": search_phrase if decision_type in {"doc", "both"} else None,
            "vector_from_sql_field": vector_from_sql_field,
            "db_file_field": db_file_field,
            "vector_prefix": item.get("vector_prefix") or "",
            "reasoning": item.get("reasoning") or "batch_objective_planner",
        })

    return normalized
