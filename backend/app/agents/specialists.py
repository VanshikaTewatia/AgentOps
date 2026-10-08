import time
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agents.state import AgentState
from app.core.logging import get_logger
from app.models.agent import ToolExecution, AgentEvent
from app.schemas.agent import EvidenceItem, ToolResultData, ToolCallData
from app.tools import get_default_tool_registry
from app.tools.base import ToolContext
from app.rag.retrieval import VectorRetriever
from app.rag.embeddings import get_embedding_provider
from app.schemas.rag import RAGSource

logger = get_logger(__name__)


class DiagnosticSpecialist:
    """
    Diagnostic Agent: Inspects service health, runtime telemetry, metrics, and incident records.
    Tools permitted: get_service_status, get_service_metrics, query_incidents, get_incident.
    """
    PERMITTED_TOOLS = {"get_service_status", "get_service_metrics", "query_incidents", "get_incident"}

    @classmethod
    async def execute_task(
        cls,
        task: Dict[str, Any],
        state: AgentState,
        session: AsyncSession,
    ) -> Dict[str, Any]:
        task_id = task.get("task_id", str(uuid.uuid4()))
        description = task.get("task_description", "")
        req_tools = task.get("required_tools", [])
        run_uuid = uuid.UUID(state.get("run_id", str(uuid.uuid4())))
        user_request = state.get("user_request", "")
        lower_req = f"{description} {user_request}".lower()

        logger.info(f"DiagnosticAgent starting task: {description}")
        registry = get_default_tool_registry()
        ctx = ToolContext(session=session, run_id=str(run_uuid), user_request=user_request)

        # Determine target service
        svc_name = (
            "payment-service" if "payment" in lower_req
            else "kafka" if "kafka" in lower_req
            else "redis" if "redis" in lower_req
            else "infrastructure"
        )

        tools_to_run = []
        if req_tools:
            tools_to_run = [t for t in req_tools if t in cls.PERMITTED_TOOLS]
        else:
            if "status" in lower_req or "health" in lower_req:
                tools_to_run.append("get_service_status")
            if "metric" in lower_req or "cpu" in lower_req or "connection" in lower_req or "lag" in lower_req or "exhaustion" in lower_req:
                tools_to_run.append("get_service_metrics")
            if "incident" in lower_req or "alert" in lower_req:
                tools_to_run.append("query_incidents")
            if not tools_to_run:
                tools_to_run = ["get_service_status", "get_service_metrics"]

        collected_evidence: List[EvidenceItem] = []
        tools_executed: List[str] = []
        tool_results: List[ToolResultData] = []
        errors: List[str] = []

        for tool_name in tools_to_run:
            args: Dict[str, Any] = {}
            if tool_name == "get_service_status":
                args = {"service": svc_name}
            elif tool_name == "get_service_metrics":
                args = {"service": svc_name, "timeframe": "last_30_minutes"}
            elif tool_name == "query_incidents":
                args = {"service": svc_name, "timeframe": "last_24_hours"}
            elif tool_name == "get_incident":
                args = {"incident_id": "inc-8921-pay"}

            tool_obj = registry.get(tool_name)
            sanitized_input = tool_obj.sanitize_input(args) if tool_obj else dict(args)

            exec_res = await registry.execute(name=tool_name, arguments=args, context=ctx)
            status = exec_res.get("status", "FAILED")
            output = exec_res.get("output")
            error_msg = exec_res.get("error")
            latency = exec_res.get("latency_ms", 0.0)

            # Persist tool execution
            tool_exec_rec = ToolExecution(
                id=uuid.uuid4(),
                run_id=run_uuid,
                tool_name=tool_name,
                tool_input=sanitized_input,
                tool_output=output if isinstance(output, dict) else {"result": output} if output else None,
                status=status,
                error=error_msg,
                latency_ms=latency,
            )
            session.add(tool_exec_rec)
            tools_executed.append(tool_name)

            tool_results.append(
                ToolResultData(
                    tool_call_id=f"diag-{uuid.uuid4().hex[:6]}",
                    tool_name=tool_name,
                    status=status,
                    output=output,
                    error=error_msg,
                    latency_ms=latency,
                )
            )

            if status == "SUCCESS" and output:
                # Format structured diagnostic observation
                metric_summary = ""
                if isinstance(output, dict):
                    if "db_connection_utilization_pct" in output:
                        metric_summary = (
                            f"DB conn util: {output.get('db_connection_utilization_pct')}%, "
                            f"p99 latency: {output.get('p99_latency_ms')}ms, "
                            f"error rate: {output.get('error_rate_pct')}%"
                        )
                    elif "kafka_consumer_lag_records" in output:
                        metric_summary = (
                            f"Kafka lag: {output.get('kafka_consumer_lag_records')} records, "
                            f"error rate: {output.get('error_rate_pct')}%"
                        )
                    elif "status" in output:
                        metric_summary = f"Health status: {output.get('status')}"
                    else:
                        metric_summary = str(output)[:200]
                else:
                    metric_summary = str(output)[:200]

                collected_evidence.append(
                    EvidenceItem(
                        source_type="TOOL_OUTPUT",
                        source_identifier=tool_name,
                        source_id=str(tool_exec_rec.id),
                        source_description=f"Telemetry from {tool_name} for {svc_name}",
                        originating_agent="DiagnosticAgent",
                        content=f"[FACT] {tool_name} observation for {svc_name}: {metric_summary}",
                        evidence_class="FACT",
                        confidence=1.0,
                    )
                )
            elif status == "FAILED":
                errors.append(f"DiagnosticAgent tool '{tool_name}' failed: {error_msg}")

        await session.flush()

        agent_status = "SUCCESS" if not errors else ("PARTIAL" if collected_evidence else "FAILED")
        summary_text = (
            f"DiagnosticAgent investigated {svc_name}: executed {len(tools_executed)} tools, "
            f"collected {len(collected_evidence)} telemetry facts."
        )

        return {
            "agent_name": "DiagnosticAgent",
            "task_id": task_id,
            "task_description": description,
            "status": agent_status,
            "evidence_collected": collected_evidence,
            "tools_used": tools_executed,
            "tool_results": tool_results,
            "summary": summary_text,
            "errors": errors,
        }


class KnowledgeSpecialist:
    """
    Knowledge Agent: Searches operational runbooks and retrieves documentation using Vector RAG.
    Tools permitted: search_knowledge_base.
    """
    PERMITTED_TOOLS = {"search_knowledge_base"}

    @classmethod
    async def execute_task(
        cls,
        task: Dict[str, Any],
        state: AgentState,
        session: AsyncSession,
    ) -> Dict[str, Any]:
        task_id = task.get("task_id", str(uuid.uuid4()))
        description = task.get("task_description", "")
        user_request = state.get("user_request", "")
        run_uuid = uuid.UUID(state.get("run_id", str(uuid.uuid4())))
        query = f"{description} {user_request}".strip()

        logger.info(f"KnowledgeAgent starting task: {description}")
        embedding_provider = get_embedding_provider()
        retriever = VectorRetriever(session, embedding_provider)

        collected_evidence: List[EvidenceItem] = []
        retrieved_docs: List[RAGSource] = []
        errors: List[str] = []

        try:
            new_sources = await retriever.retrieve(query=query, top_k=3)
            for src in new_sources:
                retrieved_docs.append(src)
                ev_class = "DOCUMENTATION" if src.score >= 0.85 else "INFERENCE"
                collected_evidence.append(
                    EvidenceItem(
                        source_type="RAG_CHUNK",
                        source_identifier=src.source,
                        source_id=str(src.chunk_id) if src.chunk_id else None,
                        source_description=f"Runbook: {src.document_title}",
                        originating_agent="KnowledgeAgent",
                        content=f"[{ev_class}] {src.document_title}: {src.content[:250]}...",
                        evidence_class=ev_class,
                        confidence=src.score,
                    )
                )
        except Exception as e:
            logger.error(f"KnowledgeAgent RAG retrieval error: {e}")
            errors.append(f"KnowledgeAgent retrieval failure: {str(e)}")

        summary_text = (
            f"KnowledgeAgent retrieved {len(retrieved_docs)} relevant operational runbook sections "
            f"for query '{query[:60]}'."
        )

        return {
            "agent_name": "KnowledgeAgent",
            "task_id": task_id,
            "task_description": description,
            "status": "SUCCESS" if not errors else "FAILED",
            "evidence_collected": collected_evidence,
            "retrieved_documents": retrieved_docs,
            "tools_used": ["search_knowledge_base"],
            "summary": summary_text,
            "errors": errors,
        }


class IncidentSpecialist:
    """
    Incident Agent: Analyzes active/historical incidents and prepares incident triage actions.
    Tools permitted: query_incidents, get_incident, add_incident_comment, create_incident.
    Sensitive WRITE tools (add_incident_comment, create_incident) are subject to Phase 5 approval.
    """
    PERMITTED_TOOLS = {"query_incidents", "get_incident", "add_incident_comment", "create_incident"}

    @classmethod
    async def execute_task(
        cls,
        task: Dict[str, Any],
        state: AgentState,
        session: AsyncSession,
    ) -> Dict[str, Any]:
        task_id = task.get("task_id", str(uuid.uuid4()))
        description = task.get("task_description", "")
        req_tools = task.get("required_tools", [])
        user_request = state.get("user_request", "")
        run_uuid = uuid.UUID(state.get("run_id", str(uuid.uuid4())))
        lower_req = f"{description} {user_request}".lower()

        logger.info(f"IncidentAgent starting task: {description}")
        registry = get_default_tool_registry()
        is_resumed = state.get("resume_required", False)
        approval_status = state.get("approval_status")
        approved_by = state.get("approved_by")
        rejection_reason = state.get("rejection_reason")

        ctx = ToolContext(
            session=session,
            run_id=str(run_uuid),
            user_request=user_request,
            is_pre_approved=(is_resumed and approval_status == "APPROVED"),
            approved_by=approved_by,
        )

        collected_evidence: List[EvidenceItem] = []
        tools_executed: List[str] = []
        tool_results: List[ToolResultData] = []
        errors: List[str] = []
        pending_approval_dict = None

        # Determine tools
        tools_to_run = []
        if req_tools:
            tools_to_run = [t for t in req_tools if t in cls.PERMITTED_TOOLS]
        else:
            if "create" in lower_req and "incident" in lower_req:
                tools_to_run.append("create_incident")
            elif "comment" in lower_req:
                tools_to_run.append("add_incident_comment")
            else:
                tools_to_run.append("query_incidents")

        for tool_name in tools_to_run:
            args: Dict[str, Any] = {}
            if tool_name == "create_incident":
                args = {
                    "title": "Payment service DB connection pool exhaustion",
                    "description": "Connection pool utilization exceeded 95% threshold causing transaction timeouts",
                    "severity": "HIGH",
                    "service": "payment-service",
                }
            elif tool_name == "add_incident_comment":
                args = {
                    "incident_id": "inc-8921-pay",
                    "comment": "Identified connection pool leak. Restarting pool workers.",
                }
            elif tool_name == "query_incidents":
                args = {"service": "payment-service", "timeframe": "last_24_hours"}
            elif tool_name == "get_incident":
                args = {"incident_id": "inc-8921-pay"}

            tool_obj = registry.get(tool_name)
            sanitized_input = tool_obj.sanitize_input(args) if tool_obj else dict(args)

            exec_res = await registry.execute(name=tool_name, arguments=args, context=ctx)
            status = exec_res.get("status", "FAILED")
            output = exec_res.get("output")
            error_msg = exec_res.get("error")
            latency = exec_res.get("latency_ms", 0.0)
            req_approval = exec_res.get("requires_approval", False)

            tool_results.append(
                ToolResultData(
                    tool_call_id=f"inc-{uuid.uuid4().hex[:6]}",
                    tool_name=tool_name,
                    status=status,
                    output=output,
                    error=error_msg,
                    latency_ms=latency,
                    requires_approval=req_approval,
                )
            )
            tools_executed.append(tool_name)

            # Persist ToolExecution record for all states including PENDING_APPROVAL
            tool_exec_rec = ToolExecution(
                id=uuid.uuid4(),
                run_id=run_uuid,
                tool_name=tool_name,
                tool_input=sanitized_input,
                tool_output=output if isinstance(output, dict) else {"result": output} if output else None,
                status=status,
                error=error_msg,
                latency_ms=latency,
            )
            session.add(tool_exec_rec)

            if status == "PENDING_APPROVAL" or req_approval:
                # Halt for human approval
                pending_approval_dict = {
                    "tool_name": tool_name,
                    "tool_args": sanitized_input,
                    "reason": f"Action '{tool_name}' modifies infrastructure state or creates formal tickets.",
                }
                logger.info(f"IncidentAgent tool '{tool_name}' intercepted: requires approval.")
                break

            if status == "SUCCESS" and output:
                collected_evidence.append(
                    EvidenceItem(
                        source_type="TOOL_OUTPUT",
                        source_identifier=tool_name,
                        source_id=str(tool_exec_rec.id),
                        source_description=f"Incident action telemetry: {tool_name}",
                        originating_agent="IncidentAgent",
                        content=f"[FACT] Incident telemetry from {tool_name}: {str(output)[:250]}",
                        evidence_class="FACT",
                        confidence=1.0,
                    )
                )
            elif status == "FAILED":
                errors.append(f"IncidentAgent tool '{tool_name}' failed: {error_msg}")

        await session.flush()

        agent_status = "WAITING_APPROVAL" if pending_approval_dict else ("SUCCESS" if not errors else "FAILED")
        summary_text = (
            f"IncidentAgent processed task: executed {len(tools_executed)} tools, "
            f"pending_approval={bool(pending_approval_dict)}"
        )

        return {
            "agent_name": "IncidentAgent",
            "task_id": task_id,
            "task_description": description,
            "status": agent_status,
            "evidence_collected": collected_evidence,
            "tools_used": tools_executed,
            "tool_results": tool_results,
            "summary": summary_text,
            "pending_approval": pending_approval_dict,
            "errors": errors,
        }
