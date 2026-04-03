from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
from chatbot.schema_reference import (
    DB_SCHEMA_COMPACT,
    KEYWORD_TABLE_MAP,
    DB_ONLY_TABLES,
)
import re

from core.config import settings

llm = OllamaLLM(model=settings.CHATBOT_MODEL, temperature=0)

# Intent constants used by orchestrator and telemetry.
INTENT_SCHOOL_DATA = "sql"
INTENT_SCHOOL_DOCS = "doc"
INTENT_HYBRID = "both"
INTENT_OUT_OF_SCOPE = "out_of_scope"

_DOC_KEYWORDS = {
    "policy", "policies", "rubric", "rubrics", "handbook", "guideline",
    "instructions", "syllabus", "document", "pdf",
}
_OUT_OF_SCOPE_HINTS = {
    "fifa", "cricket", "ipl", "bitcoin", "stock", "weather", "recipe", "movie",
    "politics", "prime minister", "celebrity", "programming interview",
}
_MULTI_OBJECTIVE_JOINERS = re.compile(r"\b(and|also|plus|along with|as well as|compare)\b", re.IGNORECASE)

# ─────────────────────────────────────────────────────────────────
# PROMPT 1: TYPE DECIDER  (~200 tokens)
# Tiny prompt, one job: return sql / doc / both
# ─────────────────────────────────────────────────────────────────
TYPE_DECIDER_PROMPT = PromptTemplate(
    input_variables=["query", "chat_history"],
    template="""\
    School system query classifier. Reply with ONE word only: sql, doc, or both.
    
    sql  = live data: attendance, grades, results, schedule, announcements, events, exams, assignments
    doc  = uploaded PDF content: assignment instructions, policy documents, rubrics, syllabi
    both = needs both
    
    previous history: {chat_history}
    
    Query: {query}
    
    One word:""",
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
        child_id = extra.get("child_id", "")
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


# ─────────────────────────────────────────────────────────────────
# KEYWORD PRE-ROUTER — skips LLM for obvious DB queries
# ─────────────────────────────────────────────────────────────────
def _keyword_precheck(query: str) -> str | None:
    words = re.findall(r"\b\w+\b", query.lower())
    matched = {KEYWORD_TABLE_MAP[w] for w in words if w in KEYWORD_TABLE_MAP}
    if matched and matched.issubset(DB_ONLY_TABLES):
        return "sql"
    return None


def _is_out_of_scope(query: str) -> bool:
    words = set(re.findall(r"\b\w+\b", query.lower()))
    in_domain = bool(words.intersection(set(KEYWORD_TABLE_MAP.keys()) | _DOC_KEYWORDS))
    out_scope_hit = bool(words.intersection(_OUT_OF_SCOPE_HINTS))
    return out_scope_hit and not in_domain


def _decompose_query(query: str) -> list[str]:
    if not _MULTI_OBJECTIVE_JOINERS.search(query):
        return [query.strip()]
    parts = re.split(r"\b(?:and|also|plus|along with|as well as|compare)\b", query, flags=re.IGNORECASE)
    return [p.strip(" ,.") for p in parts if p.strip(" ,.")]


# ─────────────────────────────────────────────────────────────────
# STEP 1: Decide type
# ─────────────────────────────────────────────────────────────────
def _decide_type(query: str, chat_history: list[dict]) -> str:
    precheck = _keyword_precheck(query)
    if precheck:
        print(f"🔀 Keyword router → {precheck}")
        return precheck

    raw = llm.invoke(TYPE_DECIDER_PROMPT.format(
        query=query,
        chat_history="\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in chat_history[-4:]  # last 4 messages only (token budget)
        ))).strip().lower()
    first = raw.split()[0] if raw.split() else "sql"
    result = first if first in {"sql", "doc", "both"} else "sql"
    print(f"🤖 LLM type router → '{result}' (raw='{raw}')")
    return result


def _validate_sql_for_role(sql: str, role: str, user_id: str, extra: dict) -> bool:
    """Hard enforcement — LLM output must contain the right WHERE clause."""
    if role == "student":
        return user_id.lower() in sql.lower()
    if role == "parent":
        child_id = extra.get("child_id", "")
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
    objectives = _decompose_query(query)
    decomposition_mode = len(objectives) > 1

    if _is_out_of_scope(query):
        return {
            "type": INTENT_OUT_OF_SCOPE,
            "sql": None,
            "search_phrase": None,
            "reasoning": "type=out_of_scope | sql=no | doc=no",
            "decomposition_mode": decomposition_mode,
            "objectives": objectives,
        }

    query_type = _decide_type(query, chat_history)

    sql = None
    search_phrase = None

    if query_type in ("sql", "both"):
        sql = _generate_sql(query, permission_ctx, chat_history)
        if not sql:
            print("⚠️ SQL failed → falling back to doc")
            query_type = "doc"

    if query_type in ("doc", "both"):
        search_phrase = query

    return {
        "type": query_type,
        "sql": sql,
        "search_phrase": search_phrase,
        "reasoning": f"type={query_type} | sql={'yes' if sql else 'no'} | doc={'yes' if search_phrase else 'no'}",
        "decomposition_mode": decomposition_mode,
        "objectives": objectives,
    }
