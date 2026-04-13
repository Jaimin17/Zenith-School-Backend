from typing import Any, Iterator

from langchain_ollama import OllamaLLM
from langchain_openai import ChatOpenAI

from core.config import settings


def _content_to_text(value: Any) -> str:
    if isinstance(value, str):
        return value

    content = getattr(value, "content", None)
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                else:
                    parts.append(str(item))
            else:
                parts.append(str(item))
        return "".join(parts)

    return str(value)


class UnifiedLLM:
    def __init__(self, client: Any):
        self._client = client

    def invoke(self, prompt: str) -> str:
        return _content_to_text(self._client.invoke(prompt))

    def stream(self, prompt: str) -> Iterator[str]:
        for chunk in self._client.stream(prompt):
            token = _content_to_text(chunk)
            if token:
                yield token


def create_llm(temperature: float, streaming: bool = False) -> UnifiedLLM:
    provider = settings.LLM_PROVIDER
    model = settings.effective_llm_model

    if provider == "openrouter":
        client = ChatOpenAI(
            model=model,
            api_key=settings.LLM_API_KEY,
            base_url=settings.effective_llm_base_url,
            temperature=temperature,
            streaming=streaming,
        )
        return UnifiedLLM(client)

    client = OllamaLLM(
        model=model,
        temperature=temperature,
        streaming=streaming,
    )
    return UnifiedLLM(client)
