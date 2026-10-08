import time
import uuid
from typing import Any, Dict, Optional
from langgraph.graph import StateGraph, START, END
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from app.agents.state import AgentState, create_initial_state
from app.agents.planner import planner_node
from app.agents.orchestrator import orchestrator_node, route_next_step
from app.agents.reasoning import reasoning_node
from app.agents.tool_agent import tool_execution_node_with_session
from app.agents.delegation import specialist_delegate_node_with_session
from app.agents.analysis import analysis_node
from app.agents.synthesizer import synthesizer_node
from app.agents.rag_agent import rag_node_with_session
from app.models.agent import AgentRun, AgentEvent, ToolExecution
from app.models.approval import Approval
from app.schemas.agent import (
    AgentRunResponse,
    AgentEventResponse,
    ToolExecutionResponse,
    Plan,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


def build_agent_graph(session: AsyncSession):
    """Builds and compiles the StateGraph workflow."""
    workflow = StateGraph(AgentState)

    # 1. Add Nodes
    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("reasoning", reasoning_node)

    async def _tool_node_wrapper(state: AgentState) -> Dict[str, Any]:
        return await tool_execution_node_with_session(state, session)

    workflow.add_node("tool_execution", _tool_node_wrapper)

    async def _specialist_delegate_wrapper(state: AgentState) -> Dict[str, Any]:
        return await specialist_delegate_node_with_session(state, session)

    workflow.add_node("specialist_delegate", _specialist_delegate_wrapper)

    async def _rag_node_wrapper(state: AgentState) -> Dict[str, Any]:
        return await rag_node_with_session(state, session)

    workflow.add_node("rag_node", _rag_node_wrapper)
    workflow.add_node("analysis", analysis_node)
    workflow.add_node("synthesizer", synthesizer_node)

    # 2. Add Edges
    workflow.add_edge(START, "orchestrator")

    workflow.add_conditional_edges(
        "orchestrator",
        route_next_step,
        {
            "planner": "planner",
            "reasoning": "reasoning",
            "tool_execution": "tool_execution",
            "specialist_delegate": "specialist_delegate",
            "rag_node": "rag_node",
            "analysis": "analysis",
            "synthesizer": "synthesizer",
            "__end__": END,
        },
    )

    workflow.add_edge("planner", "orchestrator")
    workflow.add_edge("reasoning", "orchestrator")
    workflow.add_edge("tool_execution", "orchestrator")
    workflow.add_edge("specialist_delegate", "orchestrator")
    workflow.add_edge("rag_node", "orchestrator")
    workflow.add_edge("analysis", "orchestrator")
    workflow.add_edge("synthesizer", END)

    return workflow.compile()


async def run_agent_workflow(
    user_request: str,
    conversation_id: Optional[str] = None,
    session: Optional[AsyncSession] = None,
) -> AgentRunResponse:
    """Executes the full multi-agent workflow and persists execution trace."""
    if session is None:
        from app.db.session import async_session_factory
        async with async_session_factory() as local_session:
            return await run_agent_workflow(user_request, conversation_id, local_session)

    run_uuid = uuid.uuid4()
    conv_id = conversation_id or f"conv-{uuid.uuid4().hex[:8]}"

    logger.info(f"Initiating Agent Run {run_uuid} for conversation '{conv_id}'")

    # 1. Initialize DB Record
    agent_run = AgentRun(
        id=run_uuid,
        conversation_id=conv_id,
        user_request=user_request,
        status="RUNNING",
    )
    session.add(agent_run)
    await session.commit()

    # Emit AGENT_STARTED event
    start_ev = AgentEvent(
        id=uuid.uuid4(),
        run_id=run_uuid,
        node_name="orchestrator",
        event_type="AGENT_STARTED",
        payload={"user_request": user_request},
        duration_ms=0.0,
    )
    session.add(start_ev)
    await session.commit()

    initial_state = create_initial_state(
        user_request=user_request,
        conversation_id=conv_id,
        run_id=str(run_uuid),
    )

    app_graph = build_agent_graph(session)
    current_state: AgentState = dict(initial_state)

    start_total_t = time.perf_counter()

    try:
        # Stream workflow node-by-node
        async for output in app_graph.astream(initial_state):
            for node_name, node_output in output.items():
                node_start_t = time.perf_counter()
                current_state.update(node_output)
                node_duration_ms = (time.perf_counter() - node_start_t) * 1000

                # Create event log
                event = AgentEvent(
                    id=uuid.uuid4(),
                    run_id=run_uuid,
                    node_name=node_name,
                    event_type="NODE_COMPLETED",
                    payload={
                        "iteration": current_state.get("iteration_count"),
                        "tool_iteration": current_state.get("tool_iteration"),
                        "status": current_state.get("execution_status"),
                        "step_index": current_state.get("current_step_index"),
                    },
                    duration_ms=round(node_duration_ms, 2),
                )
                session.add(event)
                await session.flush()

        total_duration_ms = (time.perf_counter() - start_total_t) * 1000

        # Update final run state
        plan_dict = current_state.get("plan").model_dump() if current_state.get("plan") else None
        agent_run.status = current_state.get("execution_status", "COMPLETED")
        agent_run.plan = plan_dict
        agent_run.final_answer = current_state.get("final_answer")
        agent_run.total_latency_ms = round(total_duration_ms, 2)
        agent_run.total_tokens = current_state.get("total_tokens", 0)

        # Emit AGENT_COMPLETED / AGENT_PAUSED event
        end_event_type = "AGENT_COMPLETED" if agent_run.status == "COMPLETED" else "AGENT_PAUSED"
        end_ev = AgentEvent(
            id=uuid.uuid4(),
            run_id=run_uuid,
            node_name="synthesizer",
            event_type=end_event_type,
            payload={"status": agent_run.status},
            duration_ms=round(total_duration_ms, 2),
        )
        session.add(end_ev)
        await session.commit()

    except Exception as e:
        logger.error(f"Agent execution failed with exception: {e}")
        total_duration_ms = (time.perf_counter() - start_total_t) * 1000
        agent_run.status = "FAILED"
        agent_run.error = str(e)
        agent_run.total_latency_ms = round(total_duration_ms, 2)
        await session.commit()

    # Query back run with events and tool executions eagerly loaded
    result = await session.execute(
        select(AgentRun)
        .options(
            selectinload(AgentRun.events),
            selectinload(AgentRun.tool_executions),
        )
        .where(AgentRun.id == run_uuid)
    )
    saved_run = result.scalar_one()

    tools_used = list({t.tool_name for t in saved_run.tool_executions})
    num_tool_calls = len(saved_run.tool_executions)
    agents_used = current_state.get("agents_used", ["SupervisorAgent"])
    del_count = len(current_state.get("delegated_tasks", []))
    ev_count = len(current_state.get("evidence", []))
    is_app_req = saved_run.status == "WAITING_APPROVAL"

    return AgentRunResponse(
        id=saved_run.id,
        conversation_id=saved_run.conversation_id,
        user_request=saved_run.user_request,
        status=saved_run.status,
        plan=saved_run.plan,
        final_answer=saved_run.final_answer,
        error=saved_run.error,
        total_latency_ms=saved_run.total_latency_ms,
        total_tokens=saved_run.total_tokens,
        tools_used=tools_used,
        number_of_tool_calls=num_tool_calls,
        agents_used=agents_used,
        delegation_count=del_count,
        evidence_count=ev_count,
        approval_required=is_app_req,
        created_at=saved_run.created_at,
        updated_at=saved_run.updated_at,
        events=[
            AgentEventResponse(
                id=ev.id,
                run_id=ev.run_id,
                node_name=ev.node_name,
                event_type=ev.event_type,
                payload=ev.payload or {},
                duration_ms=ev.duration_ms,
                created_at=ev.created_at,
            )
            for ev in saved_run.events
        ],
        tool_executions=[
            ToolExecutionResponse(
                id=te.id,
                run_id=te.run_id,
                tool_name=te.tool_name,
                tool_input=te.tool_input,
                tool_output=te.tool_output,
                status=te.status,
                error=te.error,
                latency_ms=te.latency_ms,
                created_at=te.created_at,
            )
            for te in saved_run.tool_executions
        ],
    )


async def resume_agent_workflow(
    run_id: uuid.UUID,
    approval_id: uuid.UUID,
    decision: str,  # "APPROVED" or "REJECTED"
    decided_by: str,
    rejection_reason: Optional[str] = None,
    session: Optional[AsyncSession] = None,
) -> AgentRunResponse:
    """
    Resumes an interrupted LangGraph workflow after a human approval/rejection decision.
    Executes the exact pending tool that was previously blocked without restarting from scratch.
    Validates logical binding between run_id and approval_id to prevent cross-run authorization.
    """
    if session is None:
        from app.db.session import async_session_factory
        async with async_session_factory() as local_session:
            return await resume_agent_workflow(
                run_id, approval_id, decision, decided_by, rejection_reason, local_session
            )

    logger.info(f"Resuming Agent Run {run_id} after human decision '{decision}' by '{decided_by}'")

    # 1. Fetch AgentRun and Approval
    run_result = await session.execute(
        select(AgentRun)
        .options(
            selectinload(AgentRun.events),
            selectinload(AgentRun.tool_executions),
        )
        .where(AgentRun.id == run_id)
    )
    agent_run = run_result.scalar_one_or_none()
    if not agent_run:
        raise ValueError(f"Agent run {run_id} not found.")

    approval_res = await session.execute(
        select(Approval).where(Approval.id == approval_id)
    )
    approval_rec = approval_res.scalar_one_or_none()
    if not approval_rec:
        raise ValueError(f"Approval record {approval_id} not found.")

    # 2. Strict Logical Binding Check: Approval must belong to this specific AgentRun
    if approval_rec.run_id != run_id:
        raise ValueError(
            f"Security Exception: Approval {approval_id} is bound to run {approval_rec.run_id}, "
            f"cannot be used for run {run_id}."
        )

    # 3. Emit AGENT_CONTINUED event
    cont_ev = AgentEvent(
        id=uuid.uuid4(),
        run_id=run_id,
        node_name="orchestrator",
        event_type="AGENT_CONTINUED",
        payload={"decision": decision, "decided_by": decided_by, "approval_id": str(approval_id)},
        duration_ms=0.0,
    )
    session.add(cont_ev)
    await session.commit()

    # 4. Construct resumed state from persisted plan and history
    plan_obj = Plan.model_validate(agent_run.plan) if agent_run.plan else None
    step_idx = 0
    if plan_obj:
        for idx, s in enumerate(plan_obj.steps):
            if s.status in ("RUNNING", "PENDING"):
                step_idx = idx
                break

    resumed_state: AgentState = {
        "user_request": agent_run.user_request,
        "conversation_id": agent_run.conversation_id,
        "run_id": str(run_id),
        "plan": plan_obj,
        "current_step_index": step_idx,
        "messages": [{"role": "user", "content": agent_run.user_request}],
        "available_tools": [],
        "requested_tool_calls": [],
        "completed_tool_calls": [],
        "tool_calls": [],
        "tool_results": [],
        "tool_iteration": len(agent_run.tool_executions),
        "pending_approval": None,
        "approval_id": str(approval_id),
        "pending_tool_name": approval_rec.tool_name,
        "pending_tool_arguments": approval_rec.tool_args,
        "approval_status": decision,
        "resume_required": True,
        "approved_by": decided_by,
        "rejection_reason": rejection_reason,
        "retrieved_documents": [],
        "evidence": [],
        "errors": [],
        "execution_errors": [],
        "final_answer": None,
        "execution_status": "RUNNING",
        "iteration_count": len(agent_run.events),
        "total_tokens": agent_run.total_tokens or 0,
    }

    app_graph = build_agent_graph(session)
    current_state: AgentState = dict(resumed_state)
    start_total_t = time.perf_counter()

    try:
        async for output in app_graph.astream(resumed_state):
            for node_name, node_output in output.items():
                node_start_t = time.perf_counter()
                current_state.update(node_output)
                node_duration_ms = (time.perf_counter() - node_start_t) * 1000

                event = AgentEvent(
                    id=uuid.uuid4(),
                    run_id=run_id,
                    node_name=node_name,
                    event_type="NODE_COMPLETED",
                    payload={
                        "iteration": current_state.get("iteration_count"),
                        "tool_iteration": current_state.get("tool_iteration"),
                        "status": current_state.get("execution_status"),
                        "step_index": current_state.get("current_step_index"),
                    },
                    duration_ms=round(node_duration_ms, 2),
                )
                session.add(event)
                await session.flush()

        total_duration_ms = (time.perf_counter() - start_total_t) * 1000

        # Update final run state
        plan_dict = current_state.get("plan").model_dump() if current_state.get("plan") else None
        agent_run.status = current_state.get("execution_status", "COMPLETED")
        agent_run.plan = plan_dict
        agent_run.final_answer = current_state.get("final_answer")
        agent_run.total_latency_ms = (agent_run.total_latency_ms or 0.0) + round(total_duration_ms, 2)

        # Emit AGENT_COMPLETED
        end_ev = AgentEvent(
            id=uuid.uuid4(),
            run_id=run_id,
            node_name="synthesizer",
            event_type="AGENT_COMPLETED",
            payload={"status": agent_run.status},
            duration_ms=round(total_duration_ms, 2),
        )
        session.add(end_ev)
        await session.commit()

    except Exception as e:
        logger.error(f"Resumed agent execution failed: {e}")
        total_duration_ms = (time.perf_counter() - start_total_t) * 1000
        agent_run.status = "FAILED"
        agent_run.error = str(e)
        await session.commit()

    # Query back run with events and tool executions
    result = await session.execute(
        select(AgentRun)
        .options(
            selectinload(AgentRun.events),
            selectinload(AgentRun.tool_executions),
        )
        .where(AgentRun.id == run_id)
    )
    saved_run = result.scalar_one()
    tools_used = list({t.tool_name for t in saved_run.tool_executions})

    return AgentRunResponse(
        id=saved_run.id,
        conversation_id=saved_run.conversation_id,
        user_request=saved_run.user_request,
        status=saved_run.status,
        plan=saved_run.plan,
        final_answer=saved_run.final_answer,
        error=saved_run.error,
        total_latency_ms=saved_run.total_latency_ms,
        total_tokens=saved_run.total_tokens,
        tools_used=tools_used,
        number_of_tool_calls=len(saved_run.tool_executions),
        created_at=saved_run.created_at,
        updated_at=saved_run.updated_at,
        events=[
            AgentEventResponse(
                id=ev.id,
                run_id=ev.run_id,
                node_name=ev.node_name,
                event_type=ev.event_type,
                payload=ev.payload or {},
                duration_ms=ev.duration_ms,
                created_at=ev.created_at,
            )
            for ev in saved_run.events
        ],
        tool_executions=[
            ToolExecutionResponse(
                id=te.id,
                run_id=te.run_id,
                tool_name=te.tool_name,
                tool_input=te.tool_input,
                tool_output=te.tool_output,
                status=te.status,
                error=te.error,
                latency_ms=te.latency_ms,
                created_at=te.created_at,
            )
            for te in saved_run.tool_executions
        ],
    )
