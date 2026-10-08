import uuid
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document, DocumentChunk
from app.core.logging import get_logger

logger = get_logger(__name__)


class DocumentRepository:
    """Async repository for Document and DocumentChunk entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_document_by_hash(self, content_hash: str) -> Optional[Document]:
        result = await self.session.execute(
            select(Document)
            .options(selectinload(Document.chunks))
            .where(Document.content_hash == content_hash)
        )
        return result.scalar_one_or_none()

    async def get_document_by_id(self, document_id: uuid.UUID) -> Optional[Document]:
        result = await self.session.execute(
            select(Document)
            .options(selectinload(Document.chunks))
            .where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def list_documents(
        self, limit: int = 50, offset: int = 0, doc_type: Optional[str] = None
    ) -> List[Document]:
        query = select(Document).options(selectinload(Document.chunks))
        if doc_type:
            query = query.where(Document.doc_type == doc_type)
        query = query.order_by(Document.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create_document(
        self,
        title: str,
        source: str,
        doc_type: str,
        content_hash: str,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Document:
        doc = Document(
            id=uuid.uuid4(),
            title=title,
            source=source,
            doc_type=doc_type,
            content_hash=content_hash,
            meta_info=meta_info or {},
        )
        self.session.add(doc)
        await self.session.flush()
        return doc

    async def add_chunks(
        self,
        document_id: uuid.UUID,
        chunks_data: List[Dict[str, Any]],
    ) -> List[DocumentChunk]:
        chunks: List[DocumentChunk] = []
        for item in chunks_data:
            chunk = DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=item["chunk_index"],
                content=item["content"],
                embedding=item.get("embedding"),
                meta_info=item.get("meta_info", {}),
            )
            chunks.append(chunk)
            self.session.add(chunk)
        await self.session.flush()
        return chunks

    async def delete_document(self, document_id: uuid.UUID) -> bool:
        doc = await self.get_document_by_id(document_id)
        if not doc:
            return False
        await self.session.delete(doc)
        await self.session.flush()
        return True

    async def search_similar(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        metadata_filters: Optional[Dict[str, Any]] = None,
        doc_type: Optional[str] = None,
    ) -> List[Tuple[DocumentChunk, Document, float]]:
        """Search for top_k most similar chunks using cosine similarity."""
        query = (
            select(DocumentChunk, Document)
            .join(Document, DocumentChunk.document_id == Document.id)
        )

        if doc_type:
            query = query.where(Document.doc_type == doc_type)

        result = await self.session.execute(query)
        rows = result.all()

        if not rows:
            return []

        query_vec = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            query_norm = 1.0

        scored_results: List[Tuple[DocumentChunk, Document, float]] = []

        for chunk, doc in rows:
            # Check metadata filters if present
            if metadata_filters:
                chunk_meta = chunk.meta_info or {}
                doc_meta = doc.meta_info or {}
                combined_meta = {**doc_meta, **chunk_meta}
                matches_filters = all(
                    combined_meta.get(k) == v for k, v in metadata_filters.items()
                )
                if not matches_filters:
                    continue

            if chunk.embedding is not None:
                chunk_vec = np.array(chunk.embedding, dtype=np.float32)
                chunk_norm = np.linalg.norm(chunk_vec)
                if chunk_norm > 0:
                    similarity = float(np.dot(query_vec, chunk_vec) / (query_norm * chunk_norm))
                else:
                    similarity = 0.0
            else:
                similarity = 0.0

            scored_results.append((chunk, doc, similarity))

        # Sort by similarity score in descending order
        scored_results.sort(key=lambda x: x[2], reverse=True)
        return scored_results[:top_k]
