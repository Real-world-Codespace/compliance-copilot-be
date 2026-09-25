from functools import lru_cache

from .config import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL, ENVIRONMENT, OPENAI_API_KEY


class OpenAIEmbeddingProvider:
    def __init__(self) -> None:
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY là bắt buộc để index tài liệu ở production.")
        from langchain_openai import OpenAIEmbeddings
        self.client = OpenAIEmbeddings(model=EMBEDDING_MODEL, dimensions=EMBEDDING_DIMENSIONS, api_key=OPENAI_API_KEY)

    def documents(self, texts: list[str]) -> list[list[float]]:
        return self.client.embed_documents(texts)

    def query(self, text: str) -> list[float]:
        return self.client.embed_query(text)


@lru_cache
def get_embeddings() -> OpenAIEmbeddingProvider:
    if ENVIRONMENT == "production" and not OPENAI_API_KEY:
        raise RuntimeError("Production không cho phép embedding fallback.")
    return OpenAIEmbeddingProvider()
