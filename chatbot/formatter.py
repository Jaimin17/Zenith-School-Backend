from langchain_core.prompts import PromptTemplate

from chatbot.llm_factory import create_llm

llm = create_llm(temperature=0.3)

FORMAT_PROMPT = PromptTemplate(
    input_variables=["role", "original_query", "raw_data", "data_source", "history_text"],
    template="""
        You are a helpful, warm school assistant.
        Write in clean Markdown that is easy to scan on chat UI.
        
        Previous conversation:
        {history_text}
        
        The user is a {role} and asked: "{original_query}"
        
        Here is the raw data retrieved from {data_source}:
        {raw_data}
        
                Now write a clear, friendly, and visually polished response based ONLY on the data above.

                Formatting and tone rules (strict):
                - Start with a short friendly heading line.
                - Use **bold** for key facts: names, class, academic year, dates, counts, statuses.
                - Use lighter secondary text with *italics* for notes, caveats, and helper guidance.
                - Prefer short sections with mini-headings instead of long paragraphs.
                - If there are multiple records, use a compact table.
                - If there is a summary request, provide:
                    1) **Quick Summary**
                    2) **Key Details**
                    3) *Next helpful note* (italic)
                - If any requested part is missing, clearly state what is available and what is missing.
                - Be caring and user-friendly, but professional and concise.

                Safety and fidelity rules:
                - Do NOT add any information that is not present in raw data.
                - Do NOT guess class/year/count if missing.
                - If no useful data is available, politely say so and suggest a precise rephrase.
    """
)


def format_response(role: str, query: str, raw_data: str, data_source: str, chat_history: list[dict]) -> str:
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
    return llm.invoke(prompt)
