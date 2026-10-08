import abc
import hashlib
import math
import re
from typing import List
import httpx
import numpy as np

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingProvider(abc.ABC):
    """Abstract interface for embedding generation."""

    @abc.abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """Generate vector embedding for a single text chunk."""
        pass

    @abc.abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate vector embeddings for multiple text chunks."""
        pass


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic term-frequency & n-gram hashing embedding generator.
    Produces high cosine similarity for semantically and lexically related texts.
    """

    def __init__(self, dimension: int = 1536):
        self.dimension = dimension

    def _generate_vector(self, text: str) -> List[float]:
        if not text:
            v = np.zeros(self.dimension, dtype=np.float32)
            v[0] = 1.0
            return v.tolist()

        # Extract normalized alpha-numeric tokens and 3-grams
        tokens = re.findall(r"\b[a-zA-Z0-9_\-\.]+\b", text.lower())
        vector = np.zeros(self.dimension, dtype=np.float32)

        # 1. Unigram feature hashing with positive frequency weighting
        for token in tokens:
            h1 = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            pos1 = h1 % self.dimension
            vector[pos1] += 1.0

            # Sub-token character n-grams (3-grams) for stemming resilience
            if len(token) >= 3:
                for j in range(len(token) - 2):
                    ngram = token[j : j + 3]
                    h_ng = int(hashlib.sha1(ngram.encode("utf-8")).hexdigest(), 16)
                    pos_ng = h_ng % self.dimension
                    vector[pos_ng] += 0.3

        # 2. Bigram feature hashing
        if len(tokens) >= 2:
            for i in range(len(tokens) - 1):
                bigram = f"{tokens[i]}_{tokens[i+1]}"
                h2 = int(hashlib.sha256(bigram.encode("utf-8")).hexdigest(), 16)
                pos2 = h2 % self.dimension
                vector[pos2] += 2.0

        # L2 Normalize
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        else:
            vector[0] = 1.0

        return vector.tolist()

    async def embed_text(self, text: str) -> List[float]:
        return self._generate_vector(text)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self._generate_vector(t) for t in texts]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI / OpenAI-compatible API embedding provider."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "text-embedding-3-small",
        dimension: int = 1536,
    ):
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY must be provided when EMBEDDING_PROVIDER is 'openai'. "
                "Set OPENAI_API_KEY in your .env or environment variables."
            )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dimension = dimension

    async def embed_text(self, text: str) -> List[float]:
        batch = await self.embed_batch([text])
        return batch[0]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "input": texts,
            "model": self.model,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                sorted_embeddings = sorted(data["data"], key=lambda x: x["index"])
                return [item["embedding"] for item in sorted_embeddings]
            except httpx.HTTPStatusError as e:
                logger.error(f"OpenAI embedding request failed: {e.response.text}")
                raise RuntimeError(f"Embedding API error: {e.response.status_code} - {e.response.text}")
            except Exception as e:
                logger.error(f"Failed to connect to embedding service: {e}")
                raise RuntimeError(f"Embedding connection error: {e}")


def get_embedding_provider() -> EmbeddingProvider:
    """Factory to instantiate the configured embedding provider."""
    provider_type = (settings.EMBEDDING_PROVIDER if hasattr(settings, "EMBEDDING_PROVIDER") else "mock").lower()
    
    if provider_type == "openai":
        return OpenAIEmbeddingProvider(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.EMBEDDING_MODEL,
            dimension=settings.EMBEDDING_DIMENSION,
        )
    elif provider_type == "mock":
        return MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)
    else:
        raise ValueError(
            f"Unsupported EMBEDDING_PROVIDER '{provider_type}'. Supported providers: 'mock', 'openai'."
        )
