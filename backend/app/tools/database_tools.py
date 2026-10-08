from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.tools.base import BaseTool, ToolContext, ToolRisk, RiskLevel


class GetDatabaseStatsInput(BaseModel):
    database_name: Optional[str] = Field("agentops", description="Name of the database")


class DatabaseStatsOutput(BaseModel):
    database_name: str
    active_connections: int
    idle_connections: int
    max_connections: int
    pool_utilization_percent: float
    slow_queries_count: int


class GetDatabaseStatsTool(BaseTool[GetDatabaseStatsInput, DatabaseStatsOutput]):
    name = "get_database_stats"
    description = "Inspect database connection statistics and lock state safely (READ-ONLY)."
    input_schema = GetDatabaseStatsInput
    output_schema = DatabaseStatsOutput
    risk_type = ToolRisk.READ
    risk_level = RiskLevel.LOW
    requires_approval = False
    allowed_in_autonomous = True

    async def execute(self, params: GetDatabaseStatsInput, context: ToolContext) -> DatabaseStatsOutput:
        return DatabaseStatsOutput(
            database_name=params.database_name or "agentops",
            active_connections=96,
            idle_connections=4,
            max_connections=100,
            pool_utilization_percent=96.0,
            slow_queries_count=14,
        )
