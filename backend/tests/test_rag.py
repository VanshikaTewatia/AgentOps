import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.service import DocumentIngestionService, RAGService
from app.repositories.document_repository import DocumentRepository
from app.schemas.rag import RAGQueryRequest


@pytest.mark.asyncio
async def test_document_ingestion_service(db_session: AsyncSession):
    service = DocumentIngestionService(db_session)
    response = await service.ingest_document(
        title="Redis Runbook",
        content="When Redis reaches maximum memory limit, check eviction policy and scan keys.",
        source="runbooks/redis-runbook.md",
        doc_type="runbook",
        metadata={"category": "caching"},
    )

    assert response.document_id is not None
    assert response.total_chunks >= 1
    assert "successfully" in response.message

    # Test idempotency on same content
    idempotent_res = await service.ingest_document(
        title="Redis Runbook",
        content="When Redis reaches maximum memory limit, check eviction policy and scan keys.",
        source="runbooks/redis-runbook.md",
    )
    assert idempotent_res.document_id == response.document_id
    assert "already indexed" in idempotent_res.message


@pytest.mark.asyncio
async def test_vector_similarity_search_and_metadata_filter(db_session: AsyncSession):
    ingest_svc = DocumentIngestionService(db_session)

    # Ingest two distinct documents
    await ingest_svc.ingest_document(
        title="PostgreSQL Runbook",
        content="Diagnosing PostgreSQL lock contention and slow queries using pg_stat_activity.",
        source="runbooks/postgres.md",
        doc_type="runbook",
        metadata={"tier": "1"},
    )
    await ingest_svc.ingest_document(
        title="Frontend UI Guide",
        content="React Tailwind CSS component setup and state hydration patterns.",
        source="guides/frontend.md",
        doc_type="guide",
        metadata={"tier": "2"},
    )

    rag_service = RAGService(db_session)

    # Query for database topic
    res = await rag_service.query(query="How to diagnose postgresql lock contention?", top_k=2)
    assert len(res.sources) >= 1
    assert "postgres" in res.sources[0].source.lower()
    assert res.sources[0].score > 0.0
    assert "Based on" in res.answer or len(res.answer) > 0

    # Query with doc_type filter
    filtered_res = await rag_service.query(
        query="PostgreSQL",
        doc_type="guide",
    )
    # Since postgres doc is 'runbook', guide search should only retrieve guide doc or nothing
    for s in filtered_res.sources:
        assert s.source == "guides/frontend.md"


@pytest.mark.asyncio
async def test_rag_api_endpoints(client: AsyncClient, db_session: AsyncSession):
    # 1. Ingest via API
    ingest_payload = {
        "title": "Kafka Runbook",
        "content": "Kafka consumer group lag remediation and partition rebalancing.",
        "source": "runbooks/kafka.md",
        "doc_type": "runbook",
        "metadata": {"broker": "kafka"},
    }
    ingest_res = await client.post("/api/v1/documents/ingest", json=ingest_payload)
    assert ingest_res.status_code == 201
    doc_id = ingest_res.json()["document_id"]

    # 2. List documents
    list_res = await client.get("/api/v1/documents")
    assert list_res.status_code == 200
    docs = list_res.json()
    assert any(d["id"] == doc_id for d in docs)

    # 3. Get document details
    get_res = await client.get(f"/api/v1/documents/{doc_id}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Kafka Runbook"
    assert len(get_res.json()["chunks"]) >= 1

    # 4. Query RAG
    query_payload = {
        "query": "What to do about kafka consumer lag?",
        "top_k": 3,
    }
    rag_res = await client.post("/api/v1/rag/query", json=query_payload)
    assert rag_res.status_code == 200
    rag_data = rag_res.json()
    assert "answer" in rag_data
    assert len(rag_data["sources"]) >= 1
    assert rag_data["sources"][0]["source"] == "runbooks/kafka.md"
