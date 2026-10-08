from typing import Any, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import AgentState
from app.rag.retrieval import VectorRetriever
from app.rag.embeddings import get_embedding_provider
from app.schemas.agent import EvidenceItem
from app.schemas.rag import RAGSource
from app.core.logging import get_logger

logger = get_logger(__name__)


async def rag_node_with_session(state: AgentState, session: AsyncSession) -> Dict[str, Any]:
    """RAG node: Retrieves internal technical documents matching the current step or query."""
    user_request = state.get("user_request", "")
    plan = state.get("plan")
    step_idx = state.get("current_step_index", 0)
    existing_docs = list(state.get("retrieved_documents", []))
    existing_evidence = list(state.get("evidence", []))

    # Determine query string
    if plan and step_idx < len(plan.steps):
        current_step = plan.steps[step_idx]
        query = f"{current_step.description} {user_request}"
    else:
        query = user_request

    logger.info(f"RAG Agent executing retrieval for query: '{query[:80]}'")

    embedding_provider = get_embedding_provider()
    retriever = VectorRetriever(session, embedding_provider)

    try:
        new_sources: List[RAGSource] = await retriever.retrieve(query=query, top_k=3)
    except Exception as e:
        logger.error(f"RAG retrieval error in agent node: {e}")
        new_sources = []

    # Merge sources without duplicate chunk IDs
    existing_chunk_ids = {s.chunk_id for s in existing_docs}
    for src in new_sources:
        if src.chunk_id not in existing_chunk_ids:
            existing_docs.append(src)
            existing_chunk_ids.add(src.chunk_id)
            existing_evidence.append(
                EvidenceItem(
                    source_type="RAG_CHUNK",
                    source_identifier=src.source,
                    content=f"[{src.document_title}] {src.content[:200]}...",
                    confidence=src.score,
                )
            )

    # Mark current step as completed and advance step index
    if plan and step_idx < len(plan.steps):
        plan.steps[step_idx].status = "COMPLETED"
        plan.steps[step_idx].output = (
            f"Retrieved {len(new_sources)} relevant operational runbook sections."
            if new_sources
            else "No specific runbooks found."
        )

    return {
        "retrieved_documents": existing_docs,
        "evidence": existing_evidence,
        "plan": plan,
        "current_step_index": step_idx + 1,
    }
