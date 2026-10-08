import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_e2e_health_diagnostics(client: AsyncClient):
    """Verify backend health check reports service states."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "database_connected" in data
    assert "details" in data


@pytest.mark.asyncio
async def test_e2e_scenario1_investigate_database_exhaustion(client: AsyncClient):
    """
    Scenario 1: End-to-End Investigation
    User asks: 'Why is payment-service experiencing database exhaustion?'
    Expected: DiagnosticAgent and KnowledgeAgent invoked, evidence collected, final answer returned.
    """
    res = await client.post(
        "/api/v1/agent/run",
        json={"message": "Why is payment-service experiencing database exhaustion?"},
    )
    assert res.status_code == 200
    run_data = res.json()
    assert run_data["status"] == "COMPLETED"
    assert run_data["final_answer"] is not None
    assert len(run_data["agents_used"]) > 0 or len(run_data["tools_used"]) > 0


@pytest.mark.asyncio
async def test_e2e_scenario2_write_incident_approval_lifecycle(client: AsyncClient):
    """
    Scenario 2: End-to-End Sensitive WRITE Action & Human Approval
    User asks: 'Create a high-severity incident for payment-service.'
    Expected: Gated in WAITING_APPROVAL -> Human approves -> Resumes -> Incident persisted.
    """
    # 1. Request high-severity incident creation
    run_res = await client.post(
        "/api/v1/agent/run",
        json={"message": "Create a high-severity incident for payment-service."},
    )
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["status"] == "WAITING_APPROVAL"
    run_id = run_data["id"]

    # 2. Check pending approvals list
    appr_res = await client.get("/api/v1/approvals?status_filter=PENDING")
    assert appr_res.status_code == 200
    approvals = appr_res.json()
    matching = [a for a in approvals if a["run_id"] == run_id]
    assert len(matching) == 1
    approval_id = matching[0]["id"]

    # 3. Approve the action
    approve_res = await client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        json={"decided_by": "Lead-SRE-Automation", "reason": "Authorized incident creation"},
    )
    assert approve_res.status_code == 200
    action_data = approve_res.json()
    assert action_data["status"] == "APPROVED"
    assert action_data["agent_status"] == "COMPLETED"

    # 4. Verify incident exists in Incidents endpoint
    inc_res = await client.get("/api/v1/incidents")
    assert inc_res.status_code == 200
    incidents = inc_res.json()
    assert len(incidents) > 0


@pytest.mark.asyncio
async def test_e2e_scenario3_rejection_lifecycle(client: AsyncClient):
    """
    Scenario 3: End-to-End Rejection Handling
    User asks: 'Create a high-severity incident for payment-service.'
    Expected: WAITING_APPROVAL -> Human rejects -> Resumes safely with zero DB mutation.
    """
    run_res = await client.post(
        "/api/v1/agent/run",
        json={"message": "Create a high-severity incident for payment-service due to false alarm."},
    )
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["status"] == "WAITING_APPROVAL"
    run_id = run_data["id"]

    appr_res = await client.get("/api/v1/approvals?status_filter=PENDING")
    matching = [a for a in appr_res.json() if a["run_id"] == run_id]
    assert len(matching) == 1
    approval_id = matching[0]["id"]

    # Reject the action
    reject_res = await client.post(
        f"/api/v1/approvals/{approval_id}/reject",
        json={"decided_by": "Lead-SRE", "rejection_reason": "False alarm confirmed by telemetry"},
    )
    assert reject_res.status_code == 200
    action_data = reject_res.json()
    assert action_data["status"] == "REJECTED"
    assert action_data["agent_status"] == "COMPLETED"
    assert "rejected" in action_data["final_answer"].lower()


@pytest.mark.asyncio
async def test_e2e_scenario4_targeted_runbook_routing(client: AsyncClient):
    """
    Scenario 4: Targeted Knowledge Routing
    User asks: 'What does our Kafka runbook recommend for consumer lag?'
    Expected: Dynamic routing invokes KnowledgeAgent without DiagnosticAgent.
    """
    res = await client.post(
        "/api/v1/agent/run",
        json={"message": "What does our Kafka runbook recommend for consumer lag?"},
    )
    assert res.status_code == 200
    run_data = res.json()
    assert run_data["status"] == "COMPLETED"
    assert "KnowledgeAgent" in run_data["agents_used"]
    assert "DiagnosticAgent" not in run_data["agents_used"]


@pytest.mark.asyncio
async def test_e2e_scenario5_evaluation_benchmark(client: AsyncClient):
    """
    Scenario 5: Benchmark Evaluation Run
    Expected: evaluation executes, results persisted and queryable.
    """
    eval_res = await client.post(
        "/api/v1/evaluations/run",
        json={"dataset_name": "agentops-eval-v1", "max_cases": 3},
    )
    assert eval_res.status_code == 200
    eval_data = eval_res.json()
    assert eval_data["total_cases"] == 3
    assert eval_data["passed_cases"] == 3
    assert eval_data["routing_accuracy"] == 1.0

    eval_id = eval_data["id"]
    detail_res = await client.get(f"/api/v1/evaluations/{eval_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == eval_id
