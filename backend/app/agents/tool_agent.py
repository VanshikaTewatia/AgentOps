import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import AgentState
from app.core.logging import get_logger
from app.models.agent import ToolExecution, AgentEvent
from app.models.approval import Approval
from app.schemas.agent import ToolResultData, EvidenceItem, ApprovalRequest
from app.tools import get_default_tool_registry
from app.tools.base import ToolContext

logger = get_logger(__name__)


async def tool_execution_node_with_session(state: AgentState, session: AsyncSession) -> Dict[str, Any]:
    """
    Executes all requested tool calls safely, validates schemas, intercepts sensitive
    write tools into pending approvals (persisted in approvals table), handles resumed approvals,
    persists traces in PostgreSQL, and updates agent state.
    """
    run_id_str = state.get("run_id", str(uuid.uuid4()))
    run_uuid = uuid.UUID(run_id_str)
    requested_calls = state.get("requested_tool_calls", [])
    
    existing_tool_calls = list(state.get("tool_calls", []))
    existing_tool_results = list(state.get("tool_results", []))
    existing_evidence = list(state.get("evidence", []))
    execution_errors = list(state.get("execution_errors", []))
    plan = state.get("plan")
    step_idx = state.get("current_step_index", 0)
    tool_iter = state.get("tool_iteration", 0) + 1
    
    # Check if this node is executing a resumed approved tool
    is_resumed = state.get("resume_required", False)
    approval_status = state.get("approval_status")
    approved_by = state.get("approved_by")
    rejection_reason = state.get("rejection_reason")
    
    registry = get_default_tool_registry()
    ctx = ToolContext(
        session=session,
        run_id=run_id_str,
        user_request=state.get("user_request"),
        is_pre_approved=(is_resumed and approval_status == "APPROVED"),
        approved_by=approved_by,
    )
    
    pending_approval: Any = state.get("pending_approval")
    approval_id_str = state.get("approval_id")
    execution_status = state.get("execution_status", "RUNNING")

    # --- CASE A: RESUMED APPROVED OR REJECTED TOOL ---
    if is_resumed:
        tool_name = state.get("pending_tool_name")
        tool_args = state.get("pending_tool_arguments") or {}
        tool_obj = registry.get(tool_name) if tool_name else None

        if approval_status == "REJECTED":
            logger.info(f"Resumed execution for rejected tool '{tool_name}'. Reason: {rejection_reason}")
            tool_result = ToolResultData(
                tool_call_id=f"rejected-{uuid.uuid4().hex[:6]}",
                tool_name=tool_name or "unknown",
                status="REJECTED",
                output=None,
                error=f"Operation rejected by human approver: {rejection_reason}",
                latency_ms=0.0,
                requires_approval=False,
            )
            existing_tool_results.append(tool_result)
            existing_evidence.append(
                EvidenceItem(
                    source_type="TOOL_OUTPUT",
                    source_identifier=tool_name or "approval_gate",
                    content=f"[REJECTED] Action '{tool_name}' was not authorized: {rejection_reason}",
                    confidence=1.0,
                )
            )
            
            # Emit REJECTED event
            ev = AgentEvent(
                id=uuid.uuid4(),
                run_id=run_uuid,
                node_name="tool_execution",
                event_type="APPROVAL_REJECTED",
                payload={"tool_name": tool_name, "reason": rejection_reason, "decided_by": approved_by},
                duration_ms=0.0,
            )
            session.add(ev)
            await session.flush()

            if plan and step_idx < len(plan.steps):
                plan.steps[step_idx].status = "SKIPPED"
                plan.steps[step_idx].output = f"Operation rejected by human approver: {rejection_reason}"

            return {
                "tool_results": existing_tool_results,
                "evidence": existing_evidence,
                "requested_tool_calls": [],
                "completed_tool_calls": existing_tool_results,
                "pending_approval": None,
                "resume_required": False,
                "execution_status": "RUNNING",
                "tool_iteration": tool_iter,
                "current_step_index": step_idx + 1,
                "plan": plan,
            }

        elif approval_status == "APPROVED" and tool_name:
            logger.info(f"Resumed execution for approved tool '{tool_name}' with args {tool_args}")
            sanitized_input = tool_obj.sanitize_input(tool_args) if tool_obj else dict(tool_args)
            
            # Emit TOOL_STARTED event
            start_ev = AgentEvent(
                id=uuid.uuid4(),
                run_id=run_uuid,
                node_name="tool_execution",
                event_type="TOOL_STARTED",
                payload={"tool_name": tool_name, "is_approved": True},
                duration_ms=0.0,
            )
            session.add(start_ev)
            await session.flush()

            exec_res = await registry.execute(
                name=tool_name,
                arguments=tool_args,
                context=ctx,
            )

            status = exec_res.get("status", "FAILED")
            output = exec_res.get("output")
            error_msg = exec_res.get("error")
            latency = exec_res.get("latency_ms", 0.0)

            tool_result = ToolResultData(
                tool_call_id=f"approved-{uuid.uuid4().hex[:6]}",
                tool_name=tool_name,
                status=status,
                output=output,
                error=error_msg,
                latency_ms=latency,
                requires_approval=False,
            )
            existing_tool_results.append(tool_result)

            # Persist ToolExecution in Database
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

            # Emit TOOL_COMPLETED / TOOL_FAILED
            event_type = "TOOL_COMPLETED" if status == "SUCCESS" else "TOOL_FAILED"
            done_ev = AgentEvent(
                id=uuid.uuid4(),
                run_id=run_uuid,
                node_name="tool_execution",
                event_type=event_type,
                payload={"tool_name": tool_name, "status": status, "output": output, "error": error_msg},
                duration_ms=latency,
            )
            session.add(done_ev)

            if status == "SUCCESS" and output:
                existing_evidence.append(
                    EvidenceItem(
                        source_type="TOOL_OUTPUT",
                        source_identifier=tool_name,
                        content=f"Tool '{tool_name}' (Human Approved) output: {str(output)[:350]}",
                        confidence=1.0,
                    )
                )
            elif status == "FAILED":
                execution_errors.append(f"Approved tool '{tool_name}' failed: {error_msg}")

            await session.flush()

            if plan and step_idx < len(plan.steps):
                plan.steps[step_idx].status = "COMPLETED" if status == "SUCCESS" else "FAILED"
                plan.steps[step_idx].output = f"Executed approved tool {tool_name}."

            return {
                "tool_results": existing_tool_results,
                "evidence": existing_evidence,
                "requested_tool_calls": [],
                "completed_tool_calls": existing_tool_results,
                "pending_approval": None,
                "resume_required": False,
                "execution_status": "RUNNING",
                "tool_iteration": tool_iter,
                "current_step_index": step_idx + 1,
                "plan": plan,
            }

    # --- CASE B: NORMAL STEP TOOL EXECUTION ---
    for tc in requested_calls:
        tool_name = tc.tool_name
        tool_args = tc.tool_args
        tool_obj = registry.get(tool_name)
        
        logger.info(f"Executing tool '{tool_name}' with args {tool_args}")
        existing_tool_calls.append(tc)
        
        # 1. Sanitize tool input for persistence
        sanitized_input = tool_obj.sanitize_input(tool_args) if tool_obj else dict(tool_args)
        
        # 2. Execute via registry
        exec_res = await registry.execute(
            name=tool_name,
            arguments=tool_args,
            context=ctx,
        )
        
        status = exec_res.get("status", "FAILED")
        output = exec_res.get("output")
        error_msg = exec_res.get("error")
        latency = exec_res.get("latency_ms", 0.0)
        req_approval = exec_res.get("requires_approval", False)
        
        tool_result = ToolResultData(
            tool_call_id=tc.tool_call_id,
            tool_name=tool_name,
            status=status,
            output=output,
            error=error_msg,
            latency_ms=latency,
            requires_approval=req_approval,
        )
        existing_tool_results.append(tool_result)
        
        # 3. Persist ToolExecution in Database
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
        
        # 4. Handle Pending Approval
        if status == "PENDING_APPROVAL" or req_approval:
            approval_uuid = uuid.uuid4()
            approval_reason = f"Action '{tool_name}' modifies infrastructure state or creates formal tickets."
            
            # Persist Approval record in database
            approval_rec = Approval(
                id=approval_uuid,
                run_id=run_uuid,
                tool_name=tool_name,
                tool_args=sanitized_input,
                reason=approval_reason,
                status="PENDING",
            )
            session.add(approval_rec)

            pending_approval = ApprovalRequest(
                approval_id=approval_uuid,
                tool_name=tool_name,
                tool_args=sanitized_input,
                reason=approval_reason,
            )
            approval_id_str = str(approval_uuid)
            execution_status = "WAITING_APPROVAL"
            logger.info(f"Tool '{tool_name}' paused for approval. DB Approval ID: {approval_uuid}")
            
            # Emit approval event
            ev = AgentEvent(
                id=uuid.uuid4(),
                run_id=run_uuid,
                node_name="tool_execution",
                event_type="APPROVAL_REQUESTED",
                payload={"tool_name": tool_name, "approval_id": str(approval_uuid)},
                duration_ms=latency,
            )
            session.add(ev)

            # Store pending details in state for resumption
            state["pending_tool_name"] = tool_name
            state["pending_tool_arguments"] = sanitized_input
        
        # 5. Extract Evidence for successful executions
        if status == "SUCCESS" and output:
            summary_content = f"Tool '{tool_name}' output: {str(output)[:350]}"
            existing_evidence.append(
                EvidenceItem(
                    source_type="TOOL_OUTPUT",
                    source_identifier=tool_name,
                    content=summary_content,
                    confidence=1.0,
                )
            )
        elif status == "FAILED":
            if error_msg:
                execution_errors.append(f"Tool '{tool_name}' failed: {error_msg}")
    
    await session.flush()
    
    # Advance current step index if not paused for approval
    if plan and step_idx < len(plan.steps):
        plan.steps[step_idx].status = "COMPLETED" if execution_status != "WAITING_APPROVAL" else "PENDING"
        plan.steps[step_idx].output = f"Executed {len(requested_calls)} tool call(s)."
    
    return {
        "tool_calls": existing_tool_calls,
        "tool_results": existing_tool_results,
        "evidence": existing_evidence,
        "requested_tool_calls": [],
        "completed_tool_calls": existing_tool_results,
        "execution_errors": execution_errors,
        "pending_approval": pending_approval,
        "approval_id": approval_id_str,
        "pending_tool_name": state.get("pending_tool_name"),
        "pending_tool_arguments": state.get("pending_tool_arguments"),
        "execution_status": execution_status,
        "tool_iteration": tool_iter,
        "current_step_index": step_idx + 1 if execution_status != "WAITING_APPROVAL" else step_idx,
        "plan": plan,
    }
