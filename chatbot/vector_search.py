from chatbot.doc_ingester import get_vectorstore
import time
import re

from chatbot.telemetry import log_event, stable_hash


def _extract_exact_pdf_name(search_phrase: str) -> str | None:
    phrase = (search_phrase or "").strip()
    if not phrase or "*" in phrase or "?" in phrase:
        return None

    match = re.search(r"([A-Za-z0-9._-]+\.pdf)\b", phrase, flags=re.IGNORECASE)
    return match.group(1) if match else None

def search_documents(search_phrase: str, k: int = 4, request_id: str | None = None, subtask_id: str | None = None) -> str:
    """
    Search ChromaDB with the LLM-generated search phrase.
    Returns top-k relevant chunks as a single string.
    """

    started = time.perf_counter()
    vectorstore = get_vectorstore()
    exact_doc_name = _extract_exact_pdf_name(search_phrase)
    results = []

    if exact_doc_name:
        try:
            results = vectorstore.similarity_search(
                search_phrase,
                k=max(k, 8),
                filter={"filename": exact_doc_name},
            )
        except Exception:
            results = vectorstore.similarity_search(search_phrase, k=max(k, 8))
            results = [doc for doc in results if str(doc.metadata.get("filename", "")).lower() == exact_doc_name.lower()]
    else:
        results = vectorstore.similarity_search(search_phrase, k=k)

    if not results:
        if request_id:
            log_event(
                "vector_empty",
                request_id,
                subtask_id=subtask_id,
                query_hash=stable_hash(search_phrase),
                k=k,
                exact_filename=exact_doc_name,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
        if exact_doc_name:
            return f"No relevant content found in document '{exact_doc_name}'."
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
            exact_filename=exact_doc_name,
            source_files=source_files,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )

    return combined