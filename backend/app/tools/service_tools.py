from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.models.service import Service
from app.tools.base import BaseTool, ToolContext, ToolRisk, RiskLevel


# --- TOOL 1: get_service_status ---

class GetServiceStatusInput(BaseModel):
    service: str = Field(..., description="Name of the service (e.g. 'payment-service', 'kafka', 'redis')")


class ServiceStatusOutput(BaseModel):
    service: str
    status: str
    description: str
    owner_team: str
    repository_url: Optional[str] = None
    uptime_percentage: float = 99.95
    active_replicas: int = 4
    total_replicas: int = 4


class GetServiceStatusTool(BaseTool[GetServiceStatusInput, ServiceStatusOutput]):
    name = "get_service_status"
    description = "Retrieve runtime health, replica count, and metadata for an infrastructure service."
    input_schema = GetServiceStatusInput
    output_schema = ServiceStatusOutput
    risk_type = ToolRisk.READ
    risk_level = RiskLevel.LOW
    requires_approval = False
    allowed_in_autonomous = True

    async def execute(self, params: GetServiceStatusInput, context: ToolContext) -> ServiceStatusOutput:
        service_name = params.service.strip().lower()
        
        # Check in DB if session is provided
        if context.session:
            result = await context.session.execute(
                select(Service).where(Service.name == service_name)
            )
            svc = result.scalar_one_or_none()
            if svc:
                return ServiceStatusOutput(
                    service=svc.name,
                    status=svc.status,
                    description=svc.description,
                    owner_team=svc.owner_team,
                    repository_url=svc.repository_url,
                    uptime_percentage=98.2 if svc.status == "DEGRADED" else 99.95,
                    active_replicas=3 if svc.status == "DEGRADED" else 4,
                    total_replicas=4,
                )

        is_degraded = "payment" in service_name or "down" in service_name
        return ServiceStatusOutput(
            service=service_name,
            status="DEGRADED" if is_degraded else "HEALTHY",
            description=f"Core microservice managing {service_name} operations",
            owner_team="SRE & Core Infra",
            repository_url=f"https://github.com/agentops/{service_name}",
            uptime_percentage=98.15 if is_degraded else 99.98,
            active_replicas=2 if is_degraded else 4,
            total_replicas=4,
        )


# --- TOOL 2: get_service_metrics ---

class GetServiceMetricsInput(BaseModel):
    service: str = Field(..., description="Service identifier to query metrics for")
    timeframe: str = Field(default="last_30_minutes", description="Time window for metrics (e.g. 'last_30_minutes', 'last_1_hour')")


class ServiceMetricsOutput(BaseModel):
    service: str
    timeframe: str
    request_count: int
    error_rate_percent: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    cpu_utilization_percent: float
    memory_utilization_percent: float
    db_connection_pool_utilization_percent: float


class GetServiceMetricsTool(BaseTool[GetServiceMetricsInput, ServiceMetricsOutput]):
    name = "get_service_metrics"
    description = "Fetch real-time operational telemetry including error rates, p99 latency, CPU/memory, and DB pool utilization."
    input_schema = GetServiceMetricsInput
    output_schema = ServiceMetricsOutput
    risk_type = ToolRisk.READ
    risk_level = RiskLevel.LOW
    requires_approval = False
    allowed_in_autonomous = True

    async def execute(self, params: GetServiceMetricsInput, context: ToolContext) -> ServiceMetricsOutput:
        s_name = params.service.lower()
        if "payment" in s_name:
            return ServiceMetricsOutput(
                service=params.service,
                timeframe=params.timeframe,
                request_count=14520,
                error_rate_percent=6.8,
                p50_latency_ms=18.5,
                p95_latency_ms=340.0,
                p99_latency_ms=1250.0,
                cpu_utilization_percent=68.4,
                memory_utilization_percent=82.1,
                db_connection_pool_utilization_percent=96.5,
            )
        elif "kafka" in s_name:
            return ServiceMetricsOutput(
                service=params.service,
                timeframe=params.timeframe,
                request_count=98000,
                error_rate_percent=1.2,
                p50_latency_ms=5.0,
                p95_latency_ms=45.0,
                p99_latency_ms=210.0,
                cpu_utilization_percent=85.0,
                memory_utilization_percent=78.0,
                db_connection_pool_utilization_percent=32.0,
            )
        elif "redis" in s_name:
            return ServiceMetricsOutput(
                service=params.service,
                timeframe=params.timeframe,
                request_count=230000,
                error_rate_percent=0.8,
                p50_latency_ms=2.1,
                p95_latency_ms=85.0,
                p99_latency_ms=205.0,
                cpu_utilization_percent=74.0,
                memory_utilization_percent=95.2,
                db_connection_pool_utilization_percent=15.0,
            )
        else:
            return ServiceMetricsOutput(
                service=params.service,
                timeframe=params.timeframe,
                request_count=5000,
                error_rate_percent=0.05,
                p50_latency_ms=12.0,
                p95_latency_ms=35.0,
                p99_latency_ms=65.0,
                cpu_utilization_percent=25.0,
                memory_utilization_percent=40.0,
                db_connection_pool_utilization_percent=18.0,
            )
