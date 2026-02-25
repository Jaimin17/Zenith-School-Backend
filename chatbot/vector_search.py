from chatbot.doc_ingester import get_vectorstore

def search_documents(search_phrase: str, k: int = 4) -> str:
    """
    Search ChromaDB with the LLM-generated search phrase.
    Returns top-k relevant chunks as a single string.
    """

    vectorstore = get_vectorstore()
    results = vectorstore.similarity_search(search_phrase, k=k)

    if not results:
        return "No relevant documents found."

    combined = ""
    for i, doc in enumerate(results, 1):
        source = doc.metadata.get("filename", "Unknown document")
        combined += f"\n[Document {i} from '{source}']:\n{doc.page_content}\n"

    return combined