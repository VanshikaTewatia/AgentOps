import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.models.incident import Incident
from app.models.document import Document, DocumentChunk
from app.models.agent import AgentRun, AgentEvent, ToolExecution
from app.models.approval import Approval


@pytest.mark.asyncio
async def test_service_and_incident_creation(db_session: AsyncSession):
    # 1. Create Service
    service = Service(
        name="payment-service",
        description="Core payment processing microservice",
        status="DEGRADED",
        owner_team="Payments Engineering",
        repository_url="https://github.com/org/payment-service",
    )
    db_session.add(service)
    await db_session.commit()
    await db_session.refresh(service)

    assert service.id is not None
    assert service.name == "payment-service"

    # 2. Create Incident linked to Service
    incident = Incident(
        service_id=service.id,
        title="DB connection pool exhaustion",
        description="HikariCP connection pool exhausted under high traffic",
        severity="HIGH",
        status="INVESTIGATING",
    )
    db_session.add(incident)
    await db_session.commit()
    await db_session.refresh(incident)

    assert incident.id is not None
    assert incident.service_id == service.id

    # Verify query with relationship
    result = await db_session.execute(
        select(Service).where(Service.name == "payment-service")
    )
    fetched_service = result.scalar_one()
    assert fetched_service.name == "payment-service"


@pytest.mark.asyncio
async def test_document_and_chunks(db_session: AsyncSession):
    doc = Document(
        title="Payment Service Runbook",
        source="internal://runbooks/payment-service.md",
        doc_type="runbook",
        content_hash="abc123hash",
        meta_info={"category": "runbook", "author": "sre"},
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    chunk = DocumentChunk(
        document_id=doc.id,
        chunk_index=0,
        content="Payment service connects to PostgreSQL cluster on port 5432.",
        embedding=[0.01] * 1536,
        meta_info={"section": "database_config"},
    )
    db_session.add(chunk)
    await db_session.commit()
    await db_session.refresh(chunk)

    assert chunk.document_id == doc.id
    assert len(chunk.embedding) == 1536


@pytest.mark.asyncio
async def test_agent_run_and_execution_lifecycle(db_session: AsyncSession):
    run = AgentRun(
        conversation_id="conv-123",
        user_request="Investigate payment-service errors",
        status="RUNNING",
        plan={"steps": ["check_status", "query_metrics"]},
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)

    event = AgentEvent(
        run_id=run.id,
        node_name="planner",
        event_type="NODE_START",
        payload={"step": 1},
        duration_ms=45.2,
    )
    tool_exec = ToolExecution(
        run_id=run.id,
        tool_name="get_service_status",
        tool_input={"service": "payment-service"},
        tool_output={"status": "DEGRADED"},
        status="SUCCESS",
        latency_ms=120.5,
    )
    approval = Approval(
        run_id=run.id,
        tool_name="create_incident",
        tool_args={"title": "DB Outage", "severity": "HIGH"},
        reason="Action modifies production state",
        status="PENDING",
    )

    db_session.add_all([event, tool_exec, approval])
    await db_session.commit()

    # Query back
    result = await db_session.execute(select(AgentRun).where(AgentRun.id == run.id))
    fetched_run = result.scalar_one()
    assert fetched_run.status == "RUNNING"
    assert fetched_run.conversation_id == "conv-123"
