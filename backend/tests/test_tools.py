import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.tools import (
    ToolRegistry,
    get_default_tool_registry,
    BaseTool,
    ToolContext,
    ToolRisk,
    GetServiceStatusTool,
    GetServiceMetricsTool,
    QueryIncidentsTool,
    GetIncidentTool,
    AddIncidentCommentTool,
    CreateIncidentTool,
    SearchKnowledgeBaseTool,
    GetDatabaseStatsTool,
)
from app.tools.service_tools import GetServiceStatusInput, GetServiceMetricsInput
from app.tools.incident_tools import CreateIncidentInput, QueryIncidentsInput
from app.tools.rag_tools import SearchKnowledgeBaseInput
from app.rag.service import DocumentIngestionService


def test_tool_registry_registration_and_lookup():
    registry = get_default_tool_registry()
    tools = registry.list_available()
    assert "get_service_status" in tools
    assert "get_service_metrics" in tools
    assert "query_incidents" in tools
    assert "get_incident" in tools
    assert "add_incident_comment" in tools
    assert "create_incident" in tools
    assert "search_knowledge_base" in tools
    assert "get_database_stats" in tools

    tool = registry.get("get_service_status")
    assert tool is not None
    assert tool.name == "get_service_status"
    assert tool.risk_type == ToolRisk.READ


def test_tool_schema_definitions():
    registry = get_default_tool_registry()
    defs = registry.get_definitions()
    assert len(defs) == 8
    names = [d["function"]["name"] for d in defs]
    assert "get_service_status" in names
    assert "create_incident" in names


def test_unknown_tool_rejection():
    registry = get_default_tool_registry()
    assert registry.get("arbitrary_system_exec") is None
    with pytest.raises(ValueError) as exc:
        registry.validate_args("unknown_tool", {"arg": "val"})
    assert "Unknown tool" in str(exc.value)


@pytest.mark.asyncio
async def test_invalid_argument_rejection():
    registry = get_default_tool_registry()
    # Execute with invalid schema
    res = await registry.execute("get_service_status", {})
    assert res["status"] == "FAILED"
    assert "Invalid arguments" in res["error"]


@pytest.mark.asyncio
async def test_read_only_tool_execution(db_session: AsyncSession):
    registry = get_default_tool_registry()
    ctx = ToolContext(session=db_session)
    
    # 1. get_service_status
    status_res = await registry.execute("get_service_status", {"service": "payment-service"}, ctx)
    assert status_res["status"] == "SUCCESS"
    assert status_res["output"]["service"] == "payment-service"
    assert status_res["requires_approval"] is False

    # 2. get_service_metrics
    metrics_res = await registry.execute("get_service_metrics", {"service": "payment-service"}, ctx)
    assert metrics_res["status"] == "SUCCESS"
    assert metrics_res["output"]["db_connection_pool_utilization_percent"] > 90.0

    # 3. query_incidents
    inc_res = await registry.execute("query_incidents", {"service": "payment-service"}, ctx)
    assert inc_res["status"] == "SUCCESS"
    assert inc_res["output"]["total_found"] >= 1


@pytest.mark.asyncio
async def test_write_tool_requires_approval_interception():
    registry = get_default_tool_registry()
    
    # 1. create_incident (Sensitive WRITE)
    res = await registry.execute(
        "create_incident",
        {"title": "High CPU", "description": "CPU > 90%", "severity": "HIGH"},
    )
    assert res["status"] == "PENDING_APPROVAL"
    assert res["requires_approval"] is True
    assert "requires human approval" in res["error"]

    # 2. add_incident_comment (Sensitive WRITE)
    comment_res = await registry.execute(
        "add_incident_comment",
        {"incident_id": "inc-123", "comment": "Restarting pod"},
    )
    assert comment_res["status"] == "PENDING_APPROVAL"
    assert comment_res["requires_approval"] is True


def test_credential_sanitization():
    tool = GetServiceStatusTool()
    raw_input = {
        "service": "payment-service",
        "api_key": "secret_12345",
        "db_password": "super_secret_pw",
    }
    sanitized = tool.sanitize_input(raw_input)
    assert sanitized["service"] == "payment-service"
    assert sanitized["api_key"] == "******"
    assert sanitized["db_password"] == "******"


@pytest.mark.asyncio
async def test_search_knowledge_base_tool(db_session: AsyncSession):
    # Ingest document into DB
    ingestion = DocumentIngestionService(db_session)
    await ingestion.ingest_document(
        title="PostgreSQL Runbook",
        content="PostgreSQL active connections limit is 100. Connection pool exhaustion requires pool scaling.",
        source="runbooks/postgres.md",
        doc_type="runbook",
        metadata={"service": "postgres"},
    )
    await db_session.commit()

    registry = get_default_tool_registry()
    ctx = ToolContext(session=db_session)
    res = await registry.execute(
        "search_knowledge_base",
        {"query": "PostgreSQL connection pool exhaustion", "top_k": 2},
        ctx,
    )
    assert res["status"] == "SUCCESS"
    assert res["output"]["total_retrieved"] >= 1
    assert "runbooks/postgres.md" in [r["source"] for r in res["output"]["results"]]
