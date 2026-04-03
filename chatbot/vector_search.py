from chatbot.doc_ingester import get_vectorstore
import time

from chatbot.telemetry import log_event, stable_hash

def search_documents(search_phrase: str, k: int = 4, request_id: str | None = None, subtask_id: str | None = None) -> str:
    """
    Search ChromaDB with the LLM-generated search phrase.
    Returns top-k relevant chunks as a single string.
    """

    started = time.perf_counter()
    vectorstore = get_vectorstore()
    results = vectorstore.similarity_search(search_phrase, k=k)

    if not results:
        if request_id:
            log_event(
                "vector_empty",
                request_id,
                subtask_id=subtask_id,
                query_hash=stable_hash(search_phrase),
                k=k,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
        return "No relevant documents found."

    combined = ""
    source_files: list[str] = []
    for i, doc in enumerate(results, 1):
        source = doc.metadata.get("filename", "Unknown document")
        source_files.append(source)
        combined += f"\n[Document {i} from '{source}']:\n{doc.page_content}\n"

    if request_id:
        log_event(
            "vector_success",
            request_id,
            subtask_id=subtask_id,
            query_hash=stable_hash(search_phrase),
            k=k,
            result_count=len(results),
            source_files=source_files,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )

    return combined