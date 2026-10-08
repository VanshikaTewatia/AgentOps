import pytest
import numpy as np
from app.rag.embeddings import MockEmbeddingProvider, OpenAIEmbeddingProvider, get_embedding_provider


@pytest.mark.asyncio
async def test_mock_embedding_provider_determinism():
    provider = MockEmbeddingProvider(dimension=1536)
    text = "Payment service database connection timeout"

    vec1 = await provider.embed_text(text)
    vec2 = await provider.embed_text(text)

    assert len(vec1) == 1536
    assert vec1 == vec2

    # Check L2 normalization (length == 1.0)
    norm = np.linalg.norm(np.array(vec1))
    assert pytest.approx(norm, 0.001) == 1.0


@pytest.mark.asyncio
async def test_mock_embedding_batch():
    provider = MockEmbeddingProvider(dimension=512)
    texts = ["First chunk", "Second chunk", "Third chunk"]
    embeddings = await provider.embed_batch(texts)

    assert len(embeddings) == 3
    assert len(embeddings[0]) == 512


def test_openai_embedding_missing_api_key():
    with pytest.raises(ValueError, match="OPENAI_API_KEY must be provided"):
        OpenAIEmbeddingProvider(api_key="")
