import hashlib
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.document import Document
from app.rag.chunking import DocumentChunker
from app.rag.embeddings import EmbeddingProvider, get_embedding_provider
from app.rag.retrieval import VectorRetriever
from app.repositories.document_repository import DocumentRepository
from app.schemas.rag import RAGQueryResponse, RAGSource
from app.schemas.document import DocumentIngestResponse

logger = get_logger(__name__)


class DocumentIngestionService:
    """Service handling document parsing, chunking, embedding, and storage."""

    def __init__(self, session: AsyncSession, embedding_provider: Optional[EmbeddingProvider] = None):
        self.session = session
        self.repository = DocumentRepository(session)
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self.chunker = DocumentChunker(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )

    async def ingest_document(
        self,
        title: str,
        content: str,
        source: str,
        doc_type: str = "runbook",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DocumentIngestResponse:
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        # Check if already ingested
        existing_doc = await self.repository.get_document_by_hash(content_hash)
        if existing_doc:
            logger.info(f"Document already exists with hash {content_hash}. ID: {existing_doc.id}")
            return DocumentIngestResponse(
                document_id=existing_doc.id,
                title=existing_doc.title,
                source=existing_doc.source,
                total_chunks=len(existing_doc.chunks) if existing_doc.chunks else 0,
                message="Document already indexed (idempotent)",
            )

        # 1. Create Document Record
        doc = await self.repository.create_document(
            title=title,
            source=source,
            doc_type=doc_type,
            content_hash=content_hash,
            meta_info=metadata or {},
        )

        # 2. Chunk text
        chunks = self.chunker.chunk_text(
            text=content,
            base_metadata={
                "document_title": title,
                "source": source,
                "doc_type": doc_type,
                **(metadata or {}),
            },
        )

        # 3. Generate embeddings
        if chunks:
            chunk_texts = [c.content for c in chunks]
            embeddings = await self.embedding_provider.embed_batch(chunk_texts)

            chunks_data = []
            for i, chunk in enumerate(chunks):
                chunks_data.append(
                    {
                        "chunk_index": chunk.chunk_index,
                        "content": chunk.content,
                        "embedding": embeddings[i],
                        "meta_info": chunk.meta_info,
                    }
                )

            await self.repository.add_chunks(doc.id, chunks_data)

        await self.session.flush()

        return DocumentIngestResponse(
            document_id=doc.id,
            title=doc.title,
            source=doc.source,
            total_chunks=len(chunks),
            message="Document ingested and indexed successfully",
        )


class RAGService:
    """Service performing grounded Retrieval-Augmented Generation."""

    def __init__(self, session: AsyncSession, embedding_provider: Optional[EmbeddingProvider] = None):
        self.session = session
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self.retriever = VectorRetriever(session, self.embedding_provider)

    async def _generate_llm_response(self, query: str, sources: List[RAGSource]) -> str:
        """Call LLM or mock generator with grounded context."""
        if not sources:
            return "No relevant documents or operational runbooks were found matching your inquiry."

        context_blocks = []
        for i, src in enumerate(sources):
            context_blocks.append(
                f"[Source {i+1}]: {src.document_title} ({src.source})\n{src.content}"
            )
        context_str = "\n\n".join(context_blocks)

        system_prompt = (
            "You are an enterprise AI site reliability engineering assistant (AGENTOPS). "
            "Answer the user's technical question accurately using ONLY the provided runbook context below. "
            "Cite the specific sources used in your answer. "
            "If the context does not contain the answer, state that clearly."
        )
        user_prompt = f"Context Information:\n{context_str}\n\nQuestion: {query}"

        if settings.LLM_PROVIDER == "mock":
            # Deterministic synthesis for testing/offline environments
            top_src = sources[0]
            return (
                f"Based on [{top_src.document_title}]({top_src.source}):\n"
                f"For the inquiry regarding '{query}', relevant diagnostic actions include: "
                f"{top_src.content[:300]}..."
            )

        # Call OpenAI / compatible endpoint
        url = f"{settings.OPENAI_BASE_URL.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.LLM_MODEL,
            "temperature": settings.LLM_TEMPERATURE,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                logger.error(f"Error calling LLM: {e}")
                # Return grounded fallback summary
                return (
                    f"Retrieved {len(sources)} relevant context sources, but LLM completion failed ({e}). "
                    f"Primary context: {sources[0].content[:250]}..."
                )

    async def query(
        self,
        query: str,
        top_k: int = 5,
        metadata_filters: Optional[Dict[str, Any]] = None,
        doc_type: Optional[str] = None,
    ) -> RAGQueryResponse:
        sources = await self.retriever.retrieve(
            query=query,
            top_k=top_k,
            metadata_filters=metadata_filters,
            doc_type=doc_type,
        )

        answer = await self._generate_llm_response(query, sources)

        return RAGQueryResponse(
            query=query,
            answer=answer,
            sources=sources,
            total_retrieved=len(sources),
            model=settings.LLM_MODEL if settings.LLM_PROVIDER != "mock" else "mock-rag-engine",
        )
