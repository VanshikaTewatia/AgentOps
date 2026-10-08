import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agents.state import create_initial_state, AgentState
from app.schemas.agent import Plan, PlanStep, EvidenceItem, ToolCallData
from app.core.llm import MockLLMClient, get_llm_client
from app.agents.planner import planner_node
from app.agents.orchestrator import orchestrator_node, route_next_step
from app.agents.reasoning import reasoning_node
from app.agents.tool_agent import tool_execution_node_with_session
from app.agents.rag_agent import rag_node_with_session
from app.agents.analysis import analysis_node
from app.agents.synthesizer import synthesizer_node
from app.agents.graph import build_agent_graph, run_agent_workflow
from app.models.agent import AgentRun, AgentEvent, ToolExecution
from app.rag.service import DocumentIngestionService


def test_agent_state_creation():
    state = create_initial_state("Fix payment outage", "conv-1", "run-1")
    assert state["user_request"] == "Fix payment outage"
    assert state["conversation_id"] == "conv-1"
    assert state["run_id"] == "run-1"
    assert state["plan"] is None
    assert state["current_step_index"] == 0
    assert state["execution_status"] == "RUNNING"
    assert len(state["messages"]) == 1


def test_plan_schema_validation():
    step = PlanStep(
        step_number=1,
        description="Check database metrics",
        tool_required="get_service_metrics",
        requires_rag=False,
    )
    plan = Plan(
        task_summary="Investigate DB metrics",
        steps=[step],
        estimated_impact="MEDIUM",
    )
    assert len(plan.steps) == 1
    assert plan.steps[0].status == "PENDING"
    assert plan.estimated_impact == "MEDIUM"


@pytest.mark.asyncio
async def test_mock_llm_structured_output():
    client = MockLLMClient()
    messages = [{"role": "user", "content": "Payment service connection errors"}]
    plan = await client.generate_structured(messages, Plan)
    assert isinstance(plan, Plan)
    assert len(plan.steps) > 0
    assert "payment" in plan.task_summary.lower() or "connection" in plan.task_summary.lower()


@pytest.mark.asyncio
async def test_mock_llm_tool_calls():
    client = MockLLMClient()
    messages = [{"role": "user", "content": "Check get_service_metrics for payment-service"}]
    tool_calls = await client.decide_tool_calls(messages, [])
    assert len(tool_calls) > 0
    assert tool_calls[0].tool_name == "get_service_metrics"


@pytest.mark.asyncio
async def test_planner_node():
    state = create_initial_state("Database high CPU", "conv-2", "run-2")
    output = await planner_node(state)
    assert "plan" in output
    assert output["plan"] is not None
    assert output["current_step_index"] == 0


def test_orchestrator_routing():
    state = create_initial_state("Test query", "conv-3", "run-3")
    assert route_next_step(state) == "planner"

    # Add a plan with steps requiring tool
    step = PlanStep(step_number=1, description="Get metrics", tool_required="get_service_metrics")
    plan = Plan(task_summary="Search docs", steps=[step], estimated_impact="LOW")
    state["plan"] = plan
    state["current_step_index"] = 0
    assert route_next_step(state) == "reasoning"

    # When requested tools are present in state, route to tool_execution
    state["requested_tool_calls"] = [ToolCallData(tool_name="get_service_metrics", tool_args={"service": "pay"})]
    assert route_next_step(state) == "tool_execution"

    # Complete steps
    state["requested_tool_calls"] = []
    state["current_step_index"] = 1
    state["evidence"] = [EvidenceItem(source_type="TOOL_OUTPUT", source_identifier="get_service_metrics", content="latency", confidence=1.0)]
    assert route_next_step(state) == "analysis"

    # With classified evidence, routes to synthesizer
    state["evidence"] = [EvidenceItem(source_type="TOOL_OUTPUT", source_identifier="get_service_metrics", content="[FACT] latency", confidence=1.0)]
    assert route_next_step(state) == "synthesizer"


@pytest.mark.asyncio
async def test_tool_execution_node(db_session: AsyncSession):
    # Initialize run record in db
    run_rec = AgentRun(user_request="Test tool execution", conversation_id="conv-t", status="RUNNING")
    db_session.add(run_rec)
    await db_session.commit()

    state = create_initial_state("Check metrics", "conv-t", str(run_rec.id))
    step = PlanStep(step_number=1, description="Get metrics", tool_required="get_service_metrics")
    state["plan"] = Plan(task_summary="Inspect metrics", steps=[step])
    state["requested_tool_calls"] = [
        ToolCallData(tool_name="get_service_metrics", tool_args={"service": "payment-service"}),
    ]

    output = await tool_execution_node_with_session(state, db_session)
    state.update(output)

    assert len(state["tool_results"]) == 1
    assert state["tool_results"][0].status == "SUCCESS"
    assert len(state["evidence"]) == 1
    assert state["current_step_index"] == 1

    # Check persistence in DB
    exec_res = await db_session.execute(select(ToolExecution).where(ToolExecution.run_id == run_rec.id))
    records = exec_res.scalars().all()
    assert len(records) == 1
    assert records[0].tool_name == "get_service_metrics"


@pytest.mark.asyncio
async def test_sensitive_tool_pending_approval_halt(db_session: AsyncSession):
    response = await run_agent_workflow(
        user_request="Create a high-severity incident for payment-service database exhaustion",
        conversation_id="conv-approval-test",
        session=db_session,
    )

    assert response.status == "WAITING_APPROVAL"
    assert "Human Approval Required" in response.final_answer or "Approval" in response.final_answer
    assert any(t == "create_incident" for t in response.tools_used)

    # Verify tool execution record is in PENDING_APPROVAL status
    exec_res = await db_session.execute(
        select(ToolExecution).where(ToolExecution.run_id == response.id)
    )
    executions = exec_res.scalars().all()
    assert len(executions) >= 1
    assert any(e.status == "PENDING_APPROVAL" for e in executions)


@pytest.mark.asyncio
async def test_full_agent_workflow_and_persistence(db_session: AsyncSession):
    # Ingest document
    ingestion = DocumentIngestionService(db_session)
    await ingestion.ingest_document(
        title="Payment Runbook",
        content="Payment database pool exhaustion troubleshooting guide.",
        source="runbooks/payment.md",
        doc_type="runbook",
        metadata={"service_name": "payment-service"},
    )
    await db_session.commit()

    response = await run_agent_workflow(
        user_request="Why is payment-service experiencing database connection exhaustion?",
        conversation_id="test-conv-e2e-phase4",
        session=db_session,
    )

    assert response.status == "COMPLETED"
    assert response.final_answer is not None
    assert response.plan is not None
    assert response.number_of_tool_calls > 0
    assert len(response.tools_used) > 0
    assert len(response.events) > 0

    # Verify in DB
    run_in_db = await db_session.get(AgentRun, response.id)
    assert run_in_db is not None
    assert run_in_db.status == "COMPLETED"

    exec_res = await db_session.execute(
        select(ToolExecution).where(ToolExecution.run_id == response.id)
    )
    records = exec_res.scalars().all()
    assert len(records) > 0


@pytest.mark.asyncio
async def test_agent_api_endpoints(client: AsyncClient, db_session: AsyncSession):
    # 1. POST /api/v1/agent/run
    response = await client.post(
        "/api/v1/agent/run",
        json={"message": "Why is payment-service experiencing database connection exhaustion?", "conversation_id": "api-conv-phase4"},
    )
    assert response.status_code == 200
    data = response.json()
    run_id = data["id"]
    assert data["status"] == "COMPLETED"
    assert data["final_answer"] is not None
    assert data["number_of_tool_calls"] > 0
    assert len(data["tools_used"]) > 0

    # 2. GET /api/v1/agent/runs/{run_id}
    get_run_res = await client.get(f"/api/v1/agent/runs/{run_id}")
    assert get_run_res.status_code == 200
    run_data = get_run_res.json()
    assert run_data["id"] == run_id
    assert len(run_data["tool_executions"]) > 0
    assert run_data["tool_executions"][0]["status"] == "SUCCESS"
