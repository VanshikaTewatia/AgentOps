import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert data["app_name"] == "AGENTOPS"
    assert data["version"] == "1.0.0"
    assert "database_connected" in data
    assert "timestamp" in data
    assert "details" in data
