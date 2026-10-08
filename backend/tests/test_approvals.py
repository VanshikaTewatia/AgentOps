import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.approval import Approval
from app.models.agent import AgentRun, ToolExecution, AgentEvent
from app.models.incident import Incident
from app.agents.graph import run_agent_workflow, resume_agent_workflow
from app.tools import get_default_tool_registry
from app.tools.base import ToolContext, ExecutionPolicy


@pytest.mark.asyncio
async def test_approval_creation_and_persistence(db_session: AsyncSession):
    # Run request requiring create_incident
    response = await run_agent_workflow(
        user_request="Create a high-severity incident for payment-service database exhaustion",
        conversation_id="conv-appr-1",
        session=db_session,
    )

    assert response.status == "WAITING_APPROVAL"
    assert response.number_of_tool_calls > 0

    # Verify persisted Approval in PostgreSQL
    appr_res = await db_session.execute(select(Approval).where(Approval.run_id == response.id))
    apprs = appr_res.scalars().all()
    assert len(apprs) == 1
    appr = apprs[0]
    assert appr.tool_name == "create_incident"
    assert appr.status == "PENDING"
    assert appr.tool_args.get("severity") == "HIGH"


@pytest.mark.asyncio
async def test_approval_api_endpoints_approve_flow(client: AsyncClient, db_session: AsyncSession):
    # 1. Trigger agent run that enters WAITING_APPROVAL
    run_res = await client.post(
        "/api/v1/agent/run",
        json={"message": "Create a high-severity incident for payment-service database exhaustion", "conversation_id": "conv-api-appr"},
    )
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["status"] == "WAITING_APPROVAL"
    run_id = uuid.UUID(run_data["id"])

    # 2. GET /api/v1/approvals
    list_res = await client.get("/api/v1/approvals")
    assert list_res.status_code == 200
    approvals_list = list_res.json()
    assert len(approvals_list) >= 1
    matching = [a for a in approvals_list if a["run_id"] == str(run_id)]
    assert len(matching) == 1
    approval_id = matching[0]["id"]
    assert matching[0]["status"] == "PENDING"

    # 3. GET /api/v1/approvals/{approval_id}
    get_res = await client.get(f"/api/v1/approvals/{approval_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == approval_id

    # 4. POST /api/v1/approvals/{approval_id}/approve
    approve_res = await client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        json={"decided_by": "Senior-SRE-Lead", "reason": "Verified outage metrics"},
    )
    assert approve_res.status_code == 200
    action_data = approve_res.json()
    assert action_data["status"] == "APPROVED"
    assert action_data["agent_status"] == "COMPLETED"
    assert action_data["final_answer"] is not None

    # 5. Verify ToolExecution and Incident in database
    exec_res = await db_session.execute(select(ToolExecution).where(ToolExecution.run_id == run_id))
    execs = exec_res.scalars().all()
    # Should have successful tool execution now
    assert any(e.status == "SUCCESS" and e.tool_name == "create_incident" for e in execs)

    # 6. Verify Incident record created in DB
    inc_res = await db_session.execute(select(Incident))
    incidents = inc_res.scalars().all()
    assert len(incidents) >= 1


@pytest.mark.asyncio
async def test_approval_api_endpoints_reject_flow(client: AsyncClient, db_session: AsyncSession):
    # 1. Trigger run requiring approval
    run_res = await client.post(
        "/api/v1/agent/run",
        json={"message": "Create a high-severity incident for payment-service database exhaustion", "conversation_id": "conv-api-reject"},
    )
    run_id = uuid.UUID(run_res.json()["id"])

    # 2. Get approval
    apprs = (await db_session.execute(select(Approval).where(Approval.run_id == run_id))).scalars().all()
    approval_id = apprs[0].id

    # 3. POST /api/v1/approvals/{approval_id}/reject
    reject_res = await client.post(
        f"/api/v1/approvals/{approval_id}/reject",
        json={"decided_by": "Ops-Manager", "rejection_reason": "False positive alert. Already resolved."},
    )
    assert reject_res.status_code == 200
    data = reject_res.json()
    assert data["status"] == "REJECTED"
    assert data["agent_status"] == "COMPLETED"

    # 4. Verify no successful incident execution
    exec_res = await db_session.execute(select(ToolExecution).where(ToolExecution.run_id == run_id))
    execs = exec_res.scalars().all()
    # None should be SUCCESS for create_incident
    assert not any(e.status == "SUCCESS" for e in execs)


@pytest.mark.asyncio
async def test_double_approval_protection(client: AsyncClient, db_session: AsyncSession):
    # Create approval
    run_res = await client.post(
        "/api/v1/agent/run",
        json={"message": "Create a high-severity incident for payment-service database exhaustion", "conversation_id": "conv-double-test"},
    )
    run_id = uuid.UUID(run_res.json()["id"])
    apprs = (await db_session.execute(select(Approval).where(Approval.run_id == run_id))).scalars().all()
    approval_id = apprs[0].id

    # 1. First Approve: Succeeds
    res1 = await client.post(f"/api/v1/approvals/{approval_id}/approve", json={"decided_by": "Lead"})
    assert res1.status_code == 200

    # 2. Second Approve: 409 Conflict
    res2 = await client.post(f"/api/v1/approvals/{approval_id}/approve", json={"decided_by": "Lead2"})
    assert res2.status_code == 409
    assert "already been resolved" in res2.json()["detail"]

    # 3. Reject already approved: 409 Conflict
    res3 = await client.post(f"/api/v1/approvals/{approval_id}/reject", json={"decided_by": "Lead3", "rejection_reason": "Too late"})
    assert res3.status_code == 409


@pytest.mark.asyncio
async def test_autonomous_mode_policy(db_session: AsyncSession):
    registry = get_default_tool_registry()

    # 1. ASSISTED mode (Default): add_incident_comment requires approval
    ctx_assisted = ToolContext(session=db_session, execution_policy=ExecutionPolicy.ASSISTED)
    res_assisted = await registry.execute("add_incident_comment", {"incident_id": "inc-1", "comment": "Note"}, ctx_assisted)
    assert res_assisted["status"] == "PENDING_APPROVAL"

    # 2. AUTONOMOUS mode: add_incident_comment is allowlisted (MEDIUM risk) -> executes
    ctx_auto = ToolContext(session=db_session, execution_policy=ExecutionPolicy.AUTONOMOUS)
    res_auto = await registry.execute("add_incident_comment", {"incident_id": "inc-1", "comment": "Note"}, ctx_auto)
    assert res_auto["status"] == "SUCCESS"

    # 3. AUTONOMOUS mode: create_incident is HIGH risk -> STILL requires approval
    res_high_risk = await registry.execute(
        "create_incident",
        {"title": "Outage", "description": "Crash", "severity": "HIGH"},
        ctx_auto,
    )
    assert res_high_risk["status"] == "PENDING_APPROVAL"
    assert res_high_risk["requires_approval"] is True
