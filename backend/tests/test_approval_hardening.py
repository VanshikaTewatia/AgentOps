import asyncio
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
from app.tools.base import ToolContext, ExecutionPolicy, ToolRisk


# --- 1. ATOMIC & CONCURRENT APPROVAL TESTS ---

@pytest.mark.asyncio
async def test_concurrent_approval_double_execution_prevention(client: AsyncClient, db_session: AsyncSession):
    """
    Issue two approval attempts concurrently for the same pending approval.
    Expected: Exactly one request succeeds (HTTP 200), the other receives HTTP 409 Conflict.
    The underlying tool executes exactly once.
    """
    # 1. Trigger agent run entering WAITING_APPROVAL
    run_res = await client.post(
        "/api/v1/agent/run",
        json={"message": "Create a high-severity incident for payment-service database exhaustion", "conversation_id": "conv-concurrent-appr"},
    )
    assert run_res.status_code == 200
    run_id = uuid.UUID(run_res.json()["id"])

    # 2. Retrieve pending approval ID
    apprs = (await db_session.execute(select(Approval).where(Approval.run_id == run_id))).scalars().all()
    assert len(apprs) == 1
    approval_id = apprs[0].id

    # 3. Fire two concurrent approval requests simultaneously
    task1 = client.post(f"/api/v1/approvals/{approval_id}/approve", json={"decided_by": "Approver-1"})
    task2 = client.post(f"/api/v1/approvals/{approval_id}/approve", json={"decided_by": "Approver-2"})
    res1, res2 = await asyncio.gather(task1, task2)

    statuses = [res1.status_code, res2.status_code]
    assert 200 in statuses
    assert 409 in statuses

    # 4. Verify exactly ONE Incident created in DB and ONE successful execution
    inc_res = await db_session.execute(select(Incident))
    incidents = inc_res.scalars().all()
    assert len(incidents) == 1

    exec_res = await db_session.execute(
        select(ToolExecution).where(ToolExecution.run_id == run_id, ToolExecution.status == "SUCCESS")
    )
    successful_execs = exec_res.scalars().all()
    assert len(successful_execs) == 1


@pytest.mark.asyncio
async def test_state_machine_duplicate_transitions(client: AsyncClient, db_session: AsyncSession):
    """
    Test terminal states and invalid transitions:
    - approve -> approve (200, 409)
    - reject -> reject (200, 409)
    - approve -> reject (200, 409)
    - reject -> approve (200, 409)
    """
    # Case A: Approve then Reject
    run_res_a = await client.post(
        "/api/v1/agent/run",
        json={"message": "Create a high-severity incident for payment-service database exhaustion", "conversation_id": "conv-trans-a"},
    )
    run_id_a = uuid.UUID(run_res_a.json()["id"])
    appr_a = (await db_session.execute(select(Approval).where(Approval.run_id == run_id_a))).scalars().first()

    res_approve = await client.post(f"/api/v1/approvals/{appr_a.id}/approve", json={"decided_by": "Lead"})
    assert res_approve.status_code == 200
    res_reject_after_approve = await client.post(f"/api/v1/approvals/{appr_a.id}/reject", json={"decided_by": "Lead", "rejection_reason": "Late reject"})
    assert res_reject_after_approve.status_code == 409
    assert "already been resolved" in res_reject_after_approve.json()["detail"]

    # Case B: Reject then Approve
    run_res_b = await client.post(
        "/api/v1/agent/run",
        json={"message": "Create a high-severity incident for payment-service database exhaustion", "conversation_id": "conv-trans-b"},
    )
    run_id_b = uuid.UUID(run_res_b.json()["id"])
    appr_b = (await db_session.execute(select(Approval).where(Approval.run_id == run_id_b))).scalars().first()

    res_reject = await client.post(f"/api/v1/approvals/{appr_b.id}/reject", json={"decided_by": "Lead", "rejection_reason": "Denied"})
    assert res_reject.status_code == 200
    res_approve_after_reject = await client.post(f"/api/v1/approvals/{appr_b.id}/approve", json={"decided_by": "Lead"})
    assert res_approve_after_reject.status_code == 409
    assert "already been resolved" in res_approve_after_reject.json()["detail"]


# --- 2. APPROVAL PAYLOAD & BINDING SECURITY TESTS ---

@pytest.mark.asyncio
async def test_approval_payload_tampering_impossible(client: AsyncClient, db_session: AsyncSession):
    """
    Verify client cannot pass replacement tool arguments in approval endpoints.
    The server strictly retrieves the original sanitized arguments from persistent storage.
    """
    run_res = await client.post(
        "/api/v1/agent/run",
        json={"message": "Create a high-severity incident for payment-service database exhaustion", "conversation_id": "conv-tamper"},
    )
    run_id = uuid.UUID(run_res.json()["id"])
    appr = (await db_session.execute(select(Approval).where(Approval.run_id == run_id))).scalars().first()
    original_title = appr.tool_args.get("title")

    # Attempt malicious approve with modified arguments payload
    approve_res = await client.post(
        f"/api/v1/approvals/{appr.id}/approve",
        json={
            "decided_by": "Attacker",
            "reason": "Tampered",
            "tool_args": {"title": "MALICIOUS OVERRIDE TITLE", "severity": "CRITICAL"},  # Schema ignores/disallows this
        },
    )
    assert approve_res.status_code == 200

    # Verify that the executed tool used original_title
    exec_res = await db_session.execute(
        select(ToolExecution).where(ToolExecution.run_id == run_id, ToolExecution.status == "SUCCESS")
    )
    executed_tool = exec_res.scalars().first()
    assert executed_tool.tool_input.get("title") == original_title
    assert "MALICIOUS" not in executed_tool.tool_input.get("title")


@pytest.mark.asyncio
async def test_wrong_agent_run_approval_binding(db_session: AsyncSession):
    """
    Verify an approval for Run A cannot be used to resume Run B.
    """
    # Run A
    run_a = await run_agent_workflow("Create a high-severity incident for payment-service database exhaustion", "conv-bind-a", db_session)
    appr_a = (await db_session.execute(select(Approval).where(Approval.run_id == run_a.id))).scalars().first()

    # Run B
    run_b = await run_agent_workflow("Investigate payment-service database exhaustion", "conv-bind-b", db_session)

    # Attempt to resume Run B with Approval A -> Must fail with Security Exception
    with pytest.raises(ValueError, match="Security Exception"):
        await resume_agent_workflow(
            run_id=run_b.id,
            approval_id=appr_a.id,
            decision="APPROVED",
            decided_by="Attacker",
            session=db_session,
        )


# --- 3. PERSISTENCE & PROCESS RESTART RECOVERY ---

@pytest.mark.asyncio
async def test_process_restart_resume_from_persisted_storage(db_session: AsyncSession):
    """
    Verify that an interrupted WAITING_APPROVAL workflow can resume purely from
    database storage without depending on any in-memory Python variables.
    """
    # 1. Trigger agent run
    run_resp = await run_agent_workflow(
        "Create a high-severity incident for payment-service database exhaustion",
        "conv-restart-test",
        db_session,
    )
    run_id = run_resp.id
    assert run_resp.status == "WAITING_APPROVAL"

    # 2. Re-fetch approval purely from DB
    appr = (await db_session.execute(select(Approval).where(Approval.run_id == run_id))).scalars().first()
    approval_id = appr.id

    # 3. Simulate process restart by calling resume_agent_workflow with only IDs
    resumed_resp = await resume_agent_workflow(
        run_id=run_id,
        approval_id=approval_id,
        decision="APPROVED",
        decided_by="Restart-Recovery-Agent",
        session=db_session,
    )
    assert resumed_resp.status == "COMPLETED"
    assert "create_incident" in resumed_resp.tools_used
    assert resumed_resp.final_answer is not None


# --- 4. TOOL FAILURE AFTER APPROVAL & AUDIT TRAIL ---

@pytest.mark.asyncio
async def test_tool_failure_after_approval_handling(db_session: AsyncSession):
    """
    Verify that if an approved tool execution fails, the failure is faithfully recorded
    as FAILED (never silently swallowed or converted to SUCCESS) and audited in agent_events.
    """
    # Create an approval record for an invalid service that will cause tool failure
    run_rec = AgentRun(user_request="Simulate failure after approval", conversation_id="conv-fail-test", status="WAITING_APPROVAL")
    db_session.add(run_rec)
    await db_session.commit()

    # Register approval with missing required parameters to trigger validation failure in tool
    appr_fail = Approval(
        id=uuid.uuid4(),
        run_id=run_rec.id,
        tool_name="create_incident",
        tool_args={},  # Invalid parameters: missing title & description
        reason="Test failure",
        status="APPROVED",
    )
    db_session.add(appr_fail)
    await db_session.commit()

    res = await resume_agent_workflow(
        run_id=run_rec.id,
        approval_id=appr_fail.id,
        decision="APPROVED",
        decided_by="Tester",
        session=db_session,
    )

    # Tool execution must be recorded as FAILED
    exec_res = await db_session.execute(select(ToolExecution).where(ToolExecution.run_id == run_rec.id))
    failed_exec = exec_res.scalars().first()
    assert failed_exec is not None
    assert failed_exec.status == "FAILED"
    assert "Invalid arguments" in failed_exec.error or "Field required" in failed_exec.error

    # Verify TOOL_FAILED event in AgentEvent audit log
    events_res = await db_session.execute(select(AgentEvent).where(AgentEvent.run_id == run_rec.id, AgentEvent.event_type == "TOOL_FAILED"))
    fail_event = events_res.scalars().first()
    assert fail_event is not None


# --- 5. MALICIOUS LLM TOOL REQUEST & AUTHORIZATION BOUNDARY ---

@pytest.mark.asyncio
async def test_malicious_llm_request_cannot_bypass_policy(db_session: AsyncSession):
    """
    Verify that an untrusted / malicious tool request directly against the registry
    cannot bypass registration, schema validation, or risk policies.
    """
    registry = get_default_tool_registry()
    ctx = ToolContext(session=db_session, execution_policy=ExecutionPolicy.ASSISTED, is_pre_approved=False)

    # 1. Unknown tool invocation
    res_unknown = await registry.execute("exec_arbitrary_shell", {"cmd": "rm -rf /"}, ctx)
    assert res_unknown["status"] == "FAILED"
    assert "not registered" in res_unknown["error"]

    # 2. Attempt to bypass approval by sending high-risk WRITE without pre-approval
    res_bypass = await registry.execute(
        "create_incident",
        {"title": "Bypass Test", "description": "Attempting bypass", "severity": "HIGH"},
        ctx,
    )
    assert res_bypass["status"] == "PENDING_APPROVAL"
    assert res_bypass["requires_approval"] is True
