import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.evaluation import EvaluationRun, EvaluationCaseResult
from app.services.evaluation_service import EvaluationRunner
from app.rag.service import DocumentIngestionService


@pytest.mark.asyncio
async def test_evaluation_dataset_loading(db_session: AsyncSession):
    runner = EvaluationRunner(db_session)
    cases = runner.load_dataset()
    assert len(cases) >= 20
    assert any(c.category == "RAG retrieval" for c in cases)
    assert any(c.category == "Diagnostic reasoning" for c in cases)
    assert any(c.category == "Approval safety" for c in cases)
    assert any(c.category == "Conflict handling" for c in cases)


@pytest.mark.asyncio
async def test_evaluation_runner_execution_and_persistence(db_session: AsyncSession):
    # Seed knowledge base
    ingestion = DocumentIngestionService(db_session)
    await ingestion.ingest_document(
        title="Payment Service Runbook",
        content="Guide for payment-service database pool exhaustion and connection recovery.",
        source="runbooks/payment-service.md",
        doc_type="runbook",
        metadata={"service": "payment-service"},
    )
    await db_session.commit()

    runner = EvaluationRunner(db_session)
    # Run evaluation on first 5 cases
    run_response = await runner.run_evaluation(dataset_name="agentops-eval-v1", max_cases=5)

    assert run_response.total_cases == 5
    assert run_response.passed_cases > 0
    assert run_response.routing_accuracy >= 0.80
    assert run_response.tool_selection_accuracy >= 0.80
    assert run_response.avg_latency_ms > 0
    assert len(run_response.results) == 5

    # Check persistence in PostgreSQL
    saved_run = await db_session.get(EvaluationRun, run_response.id)
    assert saved_run is not None
    assert saved_run.dataset_name == "agentops-eval-v1"

    saved_cases = await db_session.execute(
        select(EvaluationCaseResult).where(EvaluationCaseResult.run_id == run_response.id)
    )
    cases_in_db = saved_cases.scalars().all()
    assert len(cases_in_db) == 5


@pytest.mark.asyncio
async def test_evaluation_api_endpoints(client: AsyncClient, db_session: AsyncSession):
    # 1. Trigger evaluation run via API (max_cases=3 for fast test)
    trigger_res = await client.post(
        "/api/v1/evaluations/run",
        json={"dataset_name": "agentops-eval-v1", "max_cases": 3},
    )
    assert trigger_res.status_code == 200
    data = trigger_res.json()
    run_id = data["id"]
    assert data["total_cases"] == 3
    assert data["routing_accuracy"] >= 0.0

    # 2. List evaluation runs
    list_res = await client.get("/api/v1/evaluations")
    assert list_res.status_code == 200
    runs = list_res.json()
    assert len(runs) >= 1
    assert any(r["id"] == run_id for r in runs)

    # 3. Get evaluation run by ID
    get_run_res = await client.get(f"/api/v1/evaluations/{run_id}")
    assert get_run_res.status_code == 200
    run_data = get_run_res.json()
    assert run_data["id"] == run_id

    # 4. Get evaluation run results
    results_res = await client.get(f"/api/v1/evaluations/{run_id}/results")
    assert results_res.status_code == 200
    results_data = results_res.json()
    assert len(results_data) == 3
    assert results_data[0]["case_id"] is not None
