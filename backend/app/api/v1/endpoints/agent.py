import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.agents.graph import run_agent_workflow
from app.models.agent import AgentRun, AgentEvent
from app.schemas.agent import (
    AgentRunRequest,
    AgentRunResponse,
    AgentEventResponse,
    ToolExecutionResponse,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/runs", response_model=List[AgentRunResponse], status_code=status.HTTP_200_OK)
async def list_agent_runs(
    limit: int = 50,
    offset: int = 0,
    status_filter: str = None,
    db: AsyncSession = Depends(get_db),
) -> List[AgentRunResponse]:
    """Retrieve list of historical agent runs ordered newest first."""
    stmt = (
        select(AgentRun)
        .options(
            selectinload(AgentRun.events),
            selectinload(AgentRun.tool_executions),
        )
        .order_by(AgentRun.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status_filter:
        stmt = stmt.where(AgentRun.status == status_filter.upper())

    result = await db.execute(stmt)
    runs = result.scalars().all()

    response_list = []
    for run in runs:
        tools_used = list({t.tool_name for t in run.tool_executions})
        response_list.append(
            AgentRunResponse(
                id=run.id,
                conversation_id=run.conversation_id,
                user_request=run.user_request,
                status=run.status,
                plan=run.plan,
                final_answer=run.final_answer,
                error=run.error,
                total_latency_ms=run.total_latency_ms,
                total_tokens=run.total_tokens,
                tools_used=tools_used,
                number_of_tool_calls=len(run.tool_executions),
                created_at=run.created_at,
                updated_at=run.updated_at,
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
                    for ev in run.events
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
                    for te in run.tool_executions
                ],
            )
        )
    return response_list


@router.post("/run", response_model=AgentRunResponse, status_code=status.HTTP_200_OK)
async def run_agent(
    request: AgentRunRequest,
    db: AsyncSession = Depends(get_db),
) -> AgentRunResponse:
    """
    Execute a LangGraph multi-agent run with real tool calling and execution tracing.
    Persists plan, node events, tool executions, and final synthesized answer in PostgreSQL.
    """
    try:
        response = await run_agent_workflow(
            user_request=request.message,
            conversation_id=request.conversation_id,
            session=db,
        )
        return response
    except Exception as e:
        logger.error(f"Error initiating agent workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent workflow failed: {str(e)}",
        )


@router.get("/runs/{run_id}", response_model=AgentRunResponse, status_code=status.HTTP_200_OK)
async def get_agent_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AgentRunResponse:
    """Retrieve full execution record, plan, and tool executions for a specific agent run."""
    result = await db.execute(
        select(AgentRun)
        .options(
            selectinload(AgentRun.events),
            selectinload(AgentRun.tool_executions),
        )
        .where(AgentRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent run with ID {run_id} not found.",
        )

    tools_used = list({t.tool_name for t in run.tool_executions})

    return AgentRunResponse(
        id=run.id,
        conversation_id=run.conversation_id,
        user_request=run.user_request,
        status=run.status,
        plan=run.plan,
        final_answer=run.final_answer,
        error=run.error,
        total_latency_ms=run.total_latency_ms,
        total_tokens=run.total_tokens,
        tools_used=tools_used,
        number_of_tool_calls=len(run.tool_executions),
        created_at=run.created_at,
        updated_at=run.updated_at,
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
            for ev in run.events
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
            for te in run.tool_executions
        ],
    )


@router.get("/runs/{run_id}/events", response_model=List[AgentEventResponse], status_code=status.HTTP_200_OK)
async def get_agent_run_events(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> List[AgentEventResponse]:
    """Retrieve discrete node execution events/traces for an agent run."""
    result = await db.execute(
        select(AgentEvent)
        .where(AgentEvent.run_id == run_id)
        .order_by(AgentEvent.created_at.asc())
    )
    events = result.scalars().all()
    if not events:
        run_check = await db.execute(select(AgentRun.id).where(AgentRun.id == run_id))
        if not run_check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent run with ID {run_id} not found.",
            )

    return [
        AgentEventResponse(
            id=ev.id,
            run_id=ev.run_id,
            node_name=ev.node_name,
            event_type=ev.event_type,
            payload=ev.payload or {},
            duration_ms=ev.duration_ms,
            created_at=ev.created_at,
        )
        for ev in events
    ]
