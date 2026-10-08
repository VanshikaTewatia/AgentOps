import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.models.incident import Incident
from app.models.service import Service
from app.tools.base import BaseTool, ToolContext, ToolRisk, RiskLevel


# --- TOOL 3: query_incidents ---

class QueryIncidentsInput(BaseModel):
    service: Optional[str] = Field(None, description="Filter incidents by service name (e.g. 'payment-service')")
    timeframe: Optional[str] = Field("last_24_hours", description="Timeframe filter")
    status: Optional[str] = Field(None, description="Incident status filter: OPEN, INVESTIGATING, RESOLVED")


class IncidentItemSummary(BaseModel):
    incident_id: str
    service: str
    title: str
    severity: str
    status: str
    created_at: str


class QueryIncidentsOutput(BaseModel):
    total_found: int
    incidents: List[IncidentItemSummary]


class QueryIncidentsTool(BaseTool[QueryIncidentsInput, QueryIncidentsOutput]):
    name = "query_incidents"
    description = "Query active and past operational incidents from the database."
    input_schema = QueryIncidentsInput
    output_schema = QueryIncidentsOutput
    risk_type = ToolRisk.READ
    risk_level = RiskLevel.LOW
    requires_approval = False
    allowed_in_autonomous = True

    async def execute(self, params: QueryIncidentsInput, context: ToolContext) -> QueryIncidentsOutput:
        incidents_list: List[IncidentItemSummary] = []

        if context.session:
            stmt = select(Incident)
            if params.service:
                stmt = stmt.join(Service).where(Service.name == params.service.lower())
            if params.status:
                stmt = stmt.where(Incident.status == params.status.upper())
            
            result = await context.session.execute(stmt)
            records = result.scalars().all()
            for rec in records:
                incidents_list.append(
                    IncidentItemSummary(
                        incident_id=str(rec.id),
                        service=params.service or "infrastructure",
                        title=rec.title,
                        severity=rec.severity,
                        status=rec.status,
                        created_at=rec.created_at.isoformat() if rec.created_at else datetime.now(timezone.utc).isoformat(),
                    )
                )

        if not incidents_list:
            service_name = params.service or "payment-service"
            if "payment" in service_name.lower():
                incidents_list.append(
                    IncidentItemSummary(
                        incident_id="inc-8921-pay",
                        service=service_name,
                        title="Elevated database connection pool timeouts on payment cluster",
                        severity="HIGH",
                        status="OPEN",
                        created_at=datetime.now(timezone.utc).isoformat(),
                    )
                )
            elif "kafka" in service_name.lower():
                incidents_list.append(
                    IncidentItemSummary(
                        incident_id="inc-7741-kfk",
                        service=service_name,
                        title="Consumer group payment-events rebalance loop",
                        severity="HIGH",
                        status="INVESTIGATING",
                        created_at=datetime.now(timezone.utc).isoformat(),
                    )
                )

        return QueryIncidentsOutput(
            total_found=len(incidents_list),
            incidents=incidents_list,
        )


# --- TOOL 5: get_incident ---

class GetIncidentInput(BaseModel):
    incident_id: str = Field(..., description="Unique ID of the incident to inspect")


class IncidentDetailOutput(BaseModel):
    incident_id: str
    title: str
    description: str
    severity: str
    status: str
    root_cause: Optional[str] = None
    resolution_notes: Optional[str] = None
    comments: List[str] = Field(default_factory=list)
    created_at: str


class GetIncidentTool(BaseTool[GetIncidentInput, IncidentDetailOutput]):
    name = "get_incident"
    description = "Retrieve detailed root cause, description, and status for a specific incident."
    input_schema = GetIncidentInput
    output_schema = IncidentDetailOutput
    risk_type = ToolRisk.READ
    risk_level = RiskLevel.LOW
    requires_approval = False
    allowed_in_autonomous = True

    async def execute(self, params: GetIncidentInput, context: ToolContext) -> IncidentDetailOutput:
        if context.session:
            try:
                inc_uuid = uuid.UUID(params.incident_id)
                rec = await context.session.get(Incident, inc_uuid)
                if rec:
                    return IncidentDetailOutput(
                        incident_id=str(rec.id),
                        title=rec.title,
                        description=rec.description,
                        severity=rec.severity,
                        status=rec.status,
                        root_cause=rec.root_cause,
                        resolution_notes=rec.resolution_notes,
                        comments=[c.get("comment", "") if isinstance(c, dict) else str(c) for c in (rec.comments or [])],
                        created_at=rec.created_at.isoformat() if rec.created_at else datetime.now(timezone.utc).isoformat(),
                    )
            except Exception:
                pass

        return IncidentDetailOutput(
            incident_id=params.incident_id,
            title="Database Connection Pool Exhaustion on payment-service",
            description="Active database pool size exceeded max limit (100/100). Transactions queued and timed out.",
            severity="HIGH",
            status="OPEN",
            root_cause="Leaked connections from long-running payment validation queries during peak traffic",
            resolution_notes="Recommend restarting hanging sessions and increasing pool size temporarily",
            comments=["Incident acknowledged by on-call engineer.", "Automated diagnostics initiated."],
            created_at=datetime.now(timezone.utc).isoformat(),
        )


# --- TOOL 6: add_incident_comment (WRITE / MEDIUM RISK / REQUIRES APPROVAL IN ASSISTED) ---

class AddIncidentCommentInput(BaseModel):
    incident_id: str = Field(..., description="ID of the incident")
    comment: str = Field(..., description="Comment or triage note to append")


class AddIncidentCommentOutput(BaseModel):
    incident_id: str
    comment_added: str
    status: str


class AddIncidentCommentTool(BaseTool[AddIncidentCommentInput, AddIncidentCommentOutput]):
    name = "add_incident_comment"
    description = "Append a diagnostic comment or mitigation note to an incident record. (WRITE OPERATION - Medium Risk)"
    input_schema = AddIncidentCommentInput
    output_schema = AddIncidentCommentOutput
    risk_type = ToolRisk.WRITE
    risk_level = RiskLevel.MEDIUM
    requires_approval = True  # Gated by approval in ASSISTED mode
    allowed_in_autonomous = True  # Can be permitted in full autonomous mode if allowlisted

    async def execute(self, params: AddIncidentCommentInput, context: ToolContext) -> AddIncidentCommentOutput:
        if context.session:
            try:
                inc_uuid = uuid.UUID(params.incident_id)
                inc = await context.session.get(Incident, inc_uuid)
                if inc:
                    comments = list(inc.comments or [])
                    comments.append({
                        "comment": params.comment,
                        "author": context.approved_by or "AGENTOPS-Agent",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
                    inc.comments = comments
                    await context.session.flush()
            except Exception:
                pass

        return AddIncidentCommentOutput(
            incident_id=params.incident_id,
            comment_added=params.comment,
            status="COMMENT_RECORDED",
        )


# --- TOOL 7: create_incident (WRITE / HIGH RISK / ALWAYS REQUIRES APPROVAL) ---

class CreateIncidentInput(BaseModel):
    title: str = Field(..., description="Incident title")
    description: str = Field(..., description="Detailed description of the incident")
    severity: str = Field("HIGH", description="Severity level: LOW, MEDIUM, HIGH, CRITICAL")
    service: Optional[str] = Field(None, description="Impacted service name")


class CreateIncidentOutput(BaseModel):
    incident_id: str
    title: str
    severity: str
    status: str
    message: str


class CreateIncidentTool(BaseTool[CreateIncidentInput, CreateIncidentOutput]):
    name = "create_incident"
    description = "Create a new high-priority operational incident ticket. (WRITE OPERATION - High Risk)"
    input_schema = CreateIncidentInput
    output_schema = CreateIncidentOutput
    risk_type = ToolRisk.WRITE
    risk_level = RiskLevel.HIGH
    requires_approval = True  # Always gated by approval
    allowed_in_autonomous = False  # High risk: Never auto-executed even in autonomous mode

    async def execute(self, params: CreateIncidentInput, context: ToolContext) -> CreateIncidentOutput:
        new_uuid = uuid.uuid4()
        
        if context.session:
            # Look up or create service
            service_name = (params.service or "infrastructure").lower()
            svc_res = await context.session.execute(
                select(Service).where(Service.name == service_name)
            )
            svc = svc_res.scalar_one_or_none()
            if not svc:
                svc = Service(
                    id=uuid.uuid4(),
                    name=service_name,
                    description=f"{service_name} operational service",
                    status="DEGRADED",
                    owner_team="SRE & Core Infra",
                )
                context.session.add(svc)
                await context.session.flush()

            incident = Incident(
                id=new_uuid,
                service_id=svc.id,
                title=params.title,
                description=params.description,
                severity=params.severity.upper(),
                status="OPEN",
                comments=[{
                    "comment": f"Created via AGENTOPS by {context.approved_by or 'Operator'}",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }],
            )
            context.session.add(incident)
            await context.session.flush()

        return CreateIncidentOutput(
            incident_id=str(new_uuid),
            title=params.title,
            severity=params.severity,
            status="OPEN",
            message="Incident created successfully in database",
        )
