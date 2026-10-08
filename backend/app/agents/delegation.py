import time
import uuid
from typing import Any, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import AgentState
from app.agents.specialists import (
    DiagnosticSpecialist,
    KnowledgeSpecialist,
    IncidentSpecialist,
)
from app.core.logging import get_logger
from app.models.agent import AgentEvent, ToolExecution
from app.models.approval import Approval
from app.schemas.agent import ApprovalRequest, EvidenceItem

logger = get_logger(__name__)


async def specialist_delegate_node_with_session(
    state: AgentState,
    session: AsyncSession,
) -> Dict[str, Any]:
    """
    Specialist Delegation Node: Dispatches current delegated task to the appropriate
    specialist agent (DiagnosticAgent, KnowledgeAgent, or IncidentAgent), isolates errors,
    collects structured evidence, and tracks execution traces in PostgreSQL.
    """
    run_id_str = state.get("run_id", str(uuid.uuid4()))
    run_uuid = uuid.UUID(run_id_str)
    delegated_tasks = state.get("delegated_tasks", [])
    current_task_idx = state.get("current_task_index", 0)
    existing_evidence = list(state.get("evidence", []))
    existing_tool_results = list(state.get("tool_results", []))
    existing_agent_results = list(state.get("agent_results", []))
    agents_used = list(state.get("agents_used", ["SupervisorAgent"]))
    delegation_hist = list(state.get("delegation_history", []))
    errors = list(state.get("errors", []))
    plan = state.get("plan")

    if current_task_idx >= len(delegated_tasks):
        logger.info("No further delegated tasks to execute.")
        return {
            "current_task_index": current_task_idx,
            "active_agent": "SupervisorAgent",
        }

    task = delegated_tasks[current_task_idx]
    target_agent = task.get("target_agent", "KnowledgeAgent")
    task_desc = task.get("task_description", "")
    task_id = task.get("task_id", str(uuid.uuid4()))

    if target_agent not in agents_used:
        agents_used.append(target_agent)
    delegation_hist.append(f"Supervisor -> {target_agent}: {task_desc[:60]}")

    logger.info(f"Supervisor delegating Task {current_task_idx + 1}/{len(delegated_tasks)} to {target_agent}")

    # Emit AGENT_DELEGATED & AGENT_STARTED events
    del_ev = AgentEvent(
        id=uuid.uuid4(),
        run_id=run_uuid,
        node_name="supervisor",
        event_type="AGENT_DELEGATED",
        payload={"target_agent": target_agent, "task_id": task_id, "task_description": task_desc},
        duration_ms=0.0,
    )
    start_ev = AgentEvent(
        id=uuid.uuid4(),
        run_id=run_uuid,
        node_name=target_agent,
        event_type="AGENT_STARTED",
        payload={"task_id": task_id},
        duration_ms=0.0,
    )
    session.add(del_ev)
    session.add(start_ev)
    await session.flush()

    start_t = time.perf_counter()
    specialist_result: Dict[str, Any] = {}
    failure_error: str = ""

    # Failure isolation: wrap specialist execution in try/except
    try:
        if target_agent == "DiagnosticAgent":
            specialist_result = await DiagnosticSpecialist.execute_task(task, state, session)
        elif target_agent == "KnowledgeAgent":
            specialist_result = await KnowledgeSpecialist.execute_task(task, state, session)
        elif target_agent == "IncidentAgent":
            specialist_result = await IncidentSpecialist.execute_task(task, state, session)
        else:
            raise ValueError(f"Unknown specialist agent: {target_agent}")
    except Exception as e:
        logger.error(f"Specialist '{target_agent}' failed with error: {e}")
        failure_error = str(e)
        specialist_result = {
            "agent_name": target_agent,
            "task_id": task_id,
            "task_description": task_desc,
            "status": "FAILED",
            "evidence_collected": [],
            "tools_used": [],
            "tool_results": [],
            "summary": f"{target_agent} failed: {failure_error}",
            "errors": [failure_error],
        }

    duration_ms = (time.perf_counter() - start_t) * 1000

    # Process specialist output
    new_evidence = specialist_result.get("evidence_collected", [])
    new_tool_results = specialist_result.get("tool_results", [])
    specialist_status = specialist_result.get("status", "SUCCESS")
    spec_errors = specialist_result.get("errors", [])
    pending_approval_info = specialist_result.get("pending_approval")

    existing_evidence.extend(new_evidence)
    existing_tool_results.extend(new_tool_results)
    existing_agent_results.append(specialist_result)
    if spec_errors:
        errors.extend(spec_errors)

    # Emit EVIDENCE_COLLECTED events
    for ev_item in new_evidence:
        ev_log = AgentEvent(
            id=uuid.uuid4(),
            run_id=run_uuid,
            node_name=target_agent,
            event_type="EVIDENCE_COLLECTED",
            payload={
                "evidence_id": ev_item.evidence_id,
                "source_type": ev_item.source_type,
                "source_identifier": ev_item.source_identifier,
                "evidence_class": ev_item.evidence_class,
                "content": ev_item.content[:200],
            },
            duration_ms=0.0,
        )
        session.add(ev_log)

    # Check if intercepted by approval gate
    execution_status = "RUNNING"
    pending_approval_obj = None
    approval_id_str = state.get("approval_id")

    if pending_approval_info:
        execution_status = "WAITING_APPROVAL"
        app_uuid = uuid.uuid4()
        tool_name = pending_approval_info.get("tool_name", "")
        tool_args = pending_approval_info.get("tool_args", {})
        reason = pending_approval_info.get("reason", "")

        approval_rec = Approval(
            id=app_uuid,
            run_id=run_uuid,
            tool_name=tool_name,
            tool_args=tool_args,
            reason=reason,
            status="PENDING",
        )
        session.add(approval_rec)
        approval_id_str = str(app_uuid)

        pending_approval_obj = ApprovalRequest(
            approval_id=app_uuid,
            tool_name=tool_name,
            tool_args=tool_args,
            reason=reason,
        )

        # Emit APPROVAL_REQUESTED event
        app_ev = AgentEvent(
            id=uuid.uuid4(),
            run_id=run_uuid,
            node_name=target_agent,
            event_type="APPROVAL_REQUESTED",
            payload={"tool_name": tool_name, "approval_id": approval_id_str, "agent": target_agent},
            duration_ms=0.0,
        )
        session.add(app_ev)

        state["pending_tool_name"] = tool_name
        state["pending_tool_arguments"] = tool_args

    # Emit AGENT_COMPLETED / AGENT_FAILED event
    done_event_type = "AGENT_FAILED" if specialist_status == "FAILED" else "AGENT_COMPLETED"
    done_ev = AgentEvent(
        id=uuid.uuid4(),
        run_id=run_uuid,
        node_name=target_agent,
        event_type=done_event_type,
        payload={"task_id": task_id, "status": specialist_status, "evidence_count": len(new_evidence)},
        duration_ms=round(duration_ms, 2),
    )
    session.add(done_ev)
    await session.flush()

    # Update plan step for backward compatibility
    if plan and current_task_idx < len(plan.steps):
        plan.steps[current_task_idx].status = (
            "COMPLETED" if specialist_status == "SUCCESS"
            else "FAILED" if specialist_status == "FAILED"
            else "PENDING"
        )
        plan.steps[current_task_idx].output = specialist_result.get("summary")

    # Advance task index only if not waiting for approval
    next_task_idx = current_task_idx + 1 if execution_status != "WAITING_APPROVAL" else current_task_idx

    return {
        "evidence": existing_evidence,
        "tool_results": existing_tool_results,
        "completed_tool_calls": existing_tool_results,
        "agent_results": existing_agent_results,
        "agents_used": agents_used,
        "delegation_history": delegation_hist,
        "errors": errors,
        "plan": plan,
        "current_task_index": next_task_idx,
        "current_step_index": next_task_idx,
        "active_agent": "SupervisorAgent",
        "execution_status": execution_status,
        "pending_approval": pending_approval_obj or state.get("pending_approval"),
        "approval_id": approval_id_str,
        "pending_tool_name": state.get("pending_tool_name"),
        "pending_tool_arguments": state.get("pending_tool_arguments"),
    }
