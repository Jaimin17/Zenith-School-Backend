from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

from core.config import settings

CHROMA_PATH = "./chroma_db"


def get_embeddings():
    """Return the configured embedding model based on EMBEDDING_PROVIDER."""
    if settings.EMBEDDING_PROVIDER == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        kwargs = dict(
            model=settings.GEMINI_EMBEDDING_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
        )
        if settings.GEMINI_EMBEDDING_DIMENSIONS is not None:
            kwargs["output_dimensionality"] = settings.GEMINI_EMBEDDING_DIMENSIONS
        return GoogleGenerativeAIEmbeddings(**kwargs)
    return OllamaEmbeddings(model=settings.OLLAMA_EMBEDDING_MODEL)


def get_vectorstore():
    """Get or create the ChromaDB vector store."""
    vectorstore = Chroma(
        persist_directory=CHROMA_PATH,
        embedding_function=get_embeddings(),
        collection_name="school_docs"
    )
    return vectorstore


def ingest_pdf(file_path: str, metadata: dict = {}):
    """
    Read a PDF, split into chunks, embed, and store in ChromaDB.
    metadata can include: {"type": "assignment", "class_id": "...", "uploaded_by": "..."}
    """

    # Step 1: Load PDF
    loader = PyPDFLoader(file_path)
    documents = loader.load()

    # Step 2: Split into smaller chunks
    # Why? LLMs have token limits, so we break docs into ~500 word pieces
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50  # overlap so context isn't lost between chunks
    )
    chunks = splitter.split_documents(documents)

    # Step 3: Add metadata to each chunk
    for chunk in chunks:
        chunk.metadata.update(metadata)

    # Step 4: Store in ChromaDB (embeddings are created automatically)
    vectorstore = get_vectorstore()
    vectorstore.add_documents(chunks)

    print(f"✅ Ingested {len(chunks)} chunks from {file_path}")
