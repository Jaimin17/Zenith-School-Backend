from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
import json, re

llm = OllamaLLM(model="llama3.2",
                temperature=0)  # temp=0 for consistent routing decisions (don't provide self-knowledge)

CLASSIFIER_PROMPT = PromptTemplate(
    input_variables=["role_description", "user_id", "scope", "allowed_tables", "extra", "query"],
    template="""
        You are a query router for a school management system.
        
        The user is: {role_description}
        Their user ID: {user_id}
        Their data scope: {scope}
        Allowed tables: {allowed_tables}
        Extra info: {extra}
        
        Based on the user's question, decide:
        1. Is this question best answered from the DATABASE (live data like grades, attendance, schedule)?
        2. Or from UPLOADED DOCUMENTS (PDFs like assignment instructions, event details, policies)?
        3. Or BOTH?
        
        Then:
        - If SQL: Write a safe read-only SQL query. ONLY use the allowed tables. 
          Always filter by user_id or relevant ID to respect data scope.
          For students: always add WHERE student_id = '{user_id}'
          For parents: always add WHERE student_id = '{extra}'
          For teachers: always filter by teacher_id = '{user_id}'
          NEVER use DROP, DELETE, UPDATE, INSERT.
        
        - If DOC: Write the best 1-sentence search phrase to find relevant document chunks.
        
        - If BOTH: Provide both SQL and search phrase.
        
        User question: {query}
        
        Respond ONLY in this exact JSON format, no extra text:
        {{
          "type": "sql" | "doc" | "both",
          "sql": "SELECT ... (or null if not sql)",
          "search_phrase": "search text... (or null if not doc)",
          "reasoning": "one line explaining your decision"
        }}
    """
)


def classify_and_generate_query(query: str, permission_ctx: dict) -> dict:
    """
    Ask LLM to classify the query and generate appropriate SQL or search phrase.
    Returns a dict with type, SQL, search_phrase.
    """

    prompt = CLASSIFIER_PROMPT.format(
        role_description=permission_ctx["description"],
        user_id=permission_ctx["user_id"],
        scope=permission_ctx["scope"],
        allowed_tables=", ".join(permission_ctx["allowed_tables"]),
        extra=str(permission_ctx.get("extra", {})),
        query=query
    )

    raw_response = llm.invoke(prompt)

    # Extract JSON from response safely
    try:
        # Sometimes LLM adds extra text, so extract JSON block
        json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return result
    except json.JSONDecodeError:
        pass

    # Fallback if LLM doesn't return clean JSON
    return {
        "type": "doc",
        "sql": None,
        "search_phrase": query,
        "reasoning": "Fallback to doc search"
    }
