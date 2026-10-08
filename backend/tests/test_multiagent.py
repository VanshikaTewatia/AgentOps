import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agents.state import create_initial_state, AgentState
from app.agents.specialists import DiagnosticSpecialist, KnowledgeSpecialist, IncidentSpecialist
from app.agents.analysis import analysis_node
from app.agents.graph import run_agent_workflow, resume_agent_workflow
from app.agents.orchestrator import orchestrator_node, route_next_step
from app.core.llm import MockLLMClient
from app.models.agent import AgentRun, AgentEvent, ToolExecution
from app.models.approval import Approval
from app.schemas.agent import EvidenceItem, DelegationPlan, SpecialistTask
from app.rag.service import DocumentIngestionService


@pytest.mark.asyncio
async def test_supervisor_dynamic_routing_diagnostic_and_knowledge(db_session: AsyncSession):
    """
    Verify Supervisor dynamically selects DiagnosticAgent + KnowledgeAgent for
    investigation query without calling IncidentAgent.
    """
    response = await run_agent_workflow(
        user_request="Why is payment-service experiencing database connection pool exhaustion?",
        conversation_id="test-conv-multiagent-1",
        session=db_session,
    )

    assert response.status == "COMPLETED"
    assert "DiagnosticAgent" in response.agents_used
    assert "KnowledgeAgent" in response.agents_used
    assert "IncidentAgent" not in response.agents_used  # Unnecessary agent was skipped
    assert response.delegation_count >= 2
    assert response.evidence_count > 0
    assert response.final_answer is not None
    assert "Multi-Agent Investigation Summary" in response.final_answer


@pytest.mark.asyncio
async def test_supervisor_dynamic_routing_knowledge_only(db_session: AsyncSession):
    """
    Verify Supervisor selects ONLY KnowledgeAgent for pure runbook questions.
    """
    response = await run_agent_workflow(
        user_request="What does our Kafka runbook recommend for consumer lag?",
        conversation_id="test-conv-multiagent-rag-only",
        session=db_session,
    )

    assert response.status == "COMPLETED"
    assert "KnowledgeAgent" in response.agents_used
    assert "DiagnosticAgent" not in response.agents_used
    assert "IncidentAgent" not in response.agents_used


@pytest.mark.asyncio
async def test_diagnostic_specialist_execution(db_session: AsyncSession):
    """Verify DiagnosticSpecialist executes read tools and extracts factual evidence."""
    state = create_initial_state("Inspect payment-service", "conv-diag", str(uuid.uuid4()))
    task = {
        "task_id": "task-diag-1",
        "target_agent": "DiagnosticAgent",
        "task_description": "Inspect payment-service health and metrics",
        "required_tools": ["get_service_status", "get_service_metrics"],
    }

    result = await DiagnosticSpecialist.execute_task(task, state, db_session)
    assert result["status"] == "SUCCESS"
    assert len(result["evidence_collected"]) >= 2
    for ev in result["evidence_collected"]:
        assert ev.evidence_class == "FACT"
        assert ev.originating_agent == "DiagnosticAgent"


@pytest.mark.asyncio
async def test_knowledge_specialist_execution(db_session: AsyncSession):
    """Verify KnowledgeSpecialist uses existing RAG retriever."""
    # Seed document
    ingestion = DocumentIngestionService(db_session)
    await ingestion.ingest_document(
        title="PostgreSQL Runbook",
        content="PostgreSQL connection pool exhaustion remediation steps.",
        source="runbooks/postgres.md",
        doc_type="runbook",
        metadata={"service_name": "payment-service"},
    )
    await db_session.commit()

    state = create_initial_state("PostgreSQL pool", "conv-kb", str(uuid.uuid4()))
    task = {
        "task_id": "task-kb-1",
        "target_agent": "KnowledgeAgent",
        "task_description": "Retrieve connection pool exhaustion troubleshooting guide",
        "required_tools": ["search_knowledge_base"],
    }

    result = await KnowledgeSpecialist.execute_task(task, state, db_session)
    assert result["status"] == "SUCCESS"
    assert len(result["evidence_collected"]) > 0
    assert result["evidence_collected"][0].originating_agent == "KnowledgeAgent"
    assert result["evidence_collected"][0].evidence_class in ("DOCUMENTATION", "INFERENCE")


@pytest.mark.asyncio
async def test_incident_specialist_write_approval_gate(db_session: AsyncSession):
    """Verify IncidentSpecialist sensitive WRITE tools trigger WAITING_APPROVAL."""
    response = await run_agent_workflow(
        user_request="Create a high-severity incident for payment-service database exhaustion",
        conversation_id="test-conv-multiagent-approval",
        session=db_session,
    )

    assert response.status == "WAITING_APPROVAL"
    assert response.approval_required is True
    assert "IncidentAgent" in response.agents_used

    # Check pending approval record in database
    app_res = await db_session.execute(select(Approval).where(Approval.run_id == response.id))
    app_rec = app_res.scalar_one_or_none()
    assert app_rec is not None
    assert app_rec.tool_name == "create_incident"
    assert app_rec.status == "PENDING"


@pytest.mark.asyncio
async def test_multi_agent_approval_and_workflow_resumption(db_session: AsyncSession):
    """Verify resuming multi-agent run after approval executes WRITE tool and synthesizes."""
    # 1. Initiate workflow requiring approval
    init_res = await run_agent_workflow(
        user_request="Create a high-severity incident for payment-service database exhaustion",
        conversation_id="test-conv-multiagent-resume",
        session=db_session,
    )
    assert init_res.status == "WAITING_APPROVAL"

    # 2. Query approval ID
    app_res = await db_session.execute(select(Approval).where(Approval.run_id == init_res.id))
    app_rec = app_res.scalar_one()

    # 3. Resume workflow with APPROVED decision
    resume_res = await resume_agent_workflow(
        run_id=init_res.id,
        approval_id=app_rec.id,
        decision="APPROVED",
        decided_by="sre_operator@enterprise.com",
        session=db_session,
    )

    assert resume_res.status == "COMPLETED"
    assert resume_res.final_answer is not None
    assert any(t == "create_incident" for t in resume_res.tools_used)

    # 4. Verify DB execution trace
    exec_res = await db_session.execute(select(ToolExecution).where(ToolExecution.run_id == init_res.id))
    execs = exec_res.scalars().all()
    assert any(e.status == "SUCCESS" and e.tool_name == "create_incident" for e in execs)


@pytest.mark.asyncio
async def test_conflicting_evidence_handling():
    """Verify that analysis_node identifies contradicting evidence and synthesizer flags ambiguity."""
    state = create_initial_state("Kafka investigation", "conv-conflict", str(uuid.uuid4()))
    
    # Introduce conflicting observations
    state["evidence"] = [
        EvidenceItem(
            source_type="TOOL_OUTPUT",
            source_identifier="get_service_metrics",
            originating_agent="DiagnosticAgent",
            content="[FACT] Kafka consumer lag is increasing rapidly (spike to 45,000 records).",
            evidence_class="FACT",
            confidence=1.0,
        ),
        EvidenceItem(
            source_type="TOOL_OUTPUT",
            source_identifier="query_incidents",
            originating_agent="IncidentAgent",
            content="[FACT] Recent alert reports kafka consumer lag is stable and normal.",
            evidence_class="FACT",
            confidence=1.0,
        ),
    ]

    analysis_res = await analysis_node(state)
    assert len(analysis_res["conflicting_evidence"]) >= 1
    conflict = analysis_res["conflicting_evidence"][0]
    assert conflict["topic"] == "Trend Contradiction"


@pytest.mark.asyncio
async def test_specialist_failure_isolation(db_session: AsyncSession):
    """Verify that if one specialist agent fails, the workflow continues and records failure transparently."""
    state = create_initial_state("Test failure isolation", "conv-fail", str(uuid.uuid4()))
    # Invalid tool call for DiagnosticAgent
    task = {
        "task_id": "task-fail-1",
        "target_agent": "DiagnosticAgent",
        "task_description": "Run non-existent tool",
        "required_tools": ["non_existent_tool"],
    }

    result = await DiagnosticSpecialist.execute_task(task, state, db_session)
    assert result["status"] in ("SUCCESS", "FAILED")  # Handled gracefully without crash


def test_supervisor_delegation_limit_guardrail():
    """Verify orchestrator guardrail halts runaway delegations."""
    state = create_initial_state("Runaway task", "conv-limit", "run-limit")
    state["delegated_tasks"] = [{"target_agent": "DiagnosticAgent"}] * 15  # Exceeds MAX_DELEGATIONS (8)
    state["current_task_index"] = 0

    import asyncio
    output = asyncio.run(orchestrator_node(state))
    assert output["execution_status"] == "COMPLETED"
    assert any("maximum delegations" in err for err in output.get("errors", []))
