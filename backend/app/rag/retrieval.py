from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.embeddings import EmbeddingProvider
from app.repositories.document_repository import DocumentRepository
from app.schemas.rag import RAGSource
from app.core.logging import get_logger

logger = get_logger(__name__)


class VectorRetriever:
    """Retrieves relevant document chunks using vector embeddings and similarity search."""

    def __init__(self, session: AsyncSession, embedding_provider: EmbeddingProvider):
        self.session = session
        self.embedding_provider = embedding_provider
        self.repository = DocumentRepository(session)

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        metadata_filters: Optional[Dict[str, Any]] = None,
        doc_type: Optional[str] = None,
    ) -> List[RAGSource]:
        query_embedding = await self.embedding_provider.embed_text(query)

        results = await self.repository.search_similar(
            query_embedding=query_embedding,
            top_k=top_k,
            metadata_filters=metadata_filters,
            doc_type=doc_type,
        )

        sources: List[RAGSource] = []
        for chunk, doc, score in results:
            sources.append(
                RAGSource(
                    document_id=doc.id,
                    document_title=doc.title,
                    source=doc.source,
                    chunk_id=chunk.id,
                    chunk_index=chunk.chunk_index,
                    score=round(score, 4),
                    content=chunk.content,
                    metadata=chunk.meta_info or {},
                )
            )

        return sources
