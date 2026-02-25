from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate

llm = OllamaLLM(model="llama3.2", temperature=0.3)

FORMAT_PROMPT = PromptTemplate(
    input_variables=["role", "original_query", "raw_data", "data_source"],
    template="""
        You are a helpful school assistant. 
        The user is a {role} and asked: "{original_query}"
        
        Here is the raw data retrieved from {data_source}:
        {raw_data}
        
        Now write a clear, friendly, and well-formatted response based ONLY on the data above.
        - If it's tabular data (grades, attendance), present it in a readable structured way
        - If it's document info, summarize it clearly
        - If there's no useful data, politely say so
        - Do NOT add any information that isn't in the raw data
        - Keep it concise
    """
)


def format_response(role: str, query: str, raw_data: str, data_source: str) -> str:
    prompt = FORMAT_PROMPT.format(
        role=role,
        original_query=query,
        raw_data=raw_data,
        data_source=data_source
    )
    return llm.invoke(prompt)
