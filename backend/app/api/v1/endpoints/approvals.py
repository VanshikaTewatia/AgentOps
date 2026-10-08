import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.db.session import get_db
from app.models.approval import Approval
from app.models.agent import AgentRun
from app.schemas.approval import (
    ApprovalResponse,
    ApprovalDecisionRequest,
    ApprovalRejectRequest,
    ApprovalActionResponse,
    ApprovalStatus,
)
from app.agents.graph import resume_agent_workflow
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("", response_model=List[ApprovalResponse], status_code=status.HTTP_200_OK)
async def list_approvals(
    status_filter: Optional[ApprovalStatus] = None,
    db: AsyncSession = Depends(get_db),
) -> List[ApprovalResponse]:
    """List all human approval requests with optional status filtering."""
    stmt = select(Approval)
    if status_filter:
        stmt = stmt.where(Approval.status == status_filter.value)
    stmt = stmt.order_by(Approval.created_at.desc())
    
    result = await db.execute(stmt)
    records = result.scalars().all()
    return [
        ApprovalResponse(
            id=rec.id,
            run_id=rec.run_id,
            tool_name=rec.tool_name,
            tool_args=rec.tool_args,
            reason=rec.reason,
            status=ApprovalStatus(rec.status),
            decided_by=rec.decided_by,
            decided_at=rec.decided_at,
            rejection_reason=rec.rejection_reason,
            created_at=rec.created_at,
            updated_at=rec.updated_at,
        )
        for rec in records
    ]


@router.get("/{approval_id}", response_model=ApprovalResponse, status_code=status.HTTP_200_OK)
async def get_approval(
    approval_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ApprovalResponse:
    """Retrieve details of a specific human approval request."""
    rec = await db.get(Approval, approval_id)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval request {approval_id} not found.",
        )
    return ApprovalResponse(
        id=rec.id,
        run_id=rec.run_id,
        tool_name=rec.tool_name,
        tool_args=rec.tool_args,
        reason=rec.reason,
        status=ApprovalStatus(rec.status),
        decided_by=rec.decided_by,
        decided_at=rec.decided_at,
        rejection_reason=rec.rejection_reason,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
    )


@router.post("/{approval_id}/approve", response_model=ApprovalActionResponse, status_code=status.HTTP_200_OK)
async def approve_request(
    approval_id: uuid.UUID,
    request: Optional[ApprovalDecisionRequest] = None,
    db: AsyncSession = Depends(get_db),
) -> ApprovalActionResponse:
    """
    Approve a pending sensitive tool invocation.
    Atomically transitions status to APPROVED using compare-and-set semantics
    to protect against race conditions and concurrent double-executions.
    """
    decided_by = request.decided_by if request else "SRE-Lead"
    now_utc = datetime.now(timezone.utc)
    
    # 1. Atomic Compare-And-Set: UPDATE ... WHERE id = :id AND status = 'PENDING'
    stmt = (
        update(Approval)
        .where(Approval.id == approval_id, Approval.status == "PENDING")
        .values(
            status="APPROVED",
            decided_by=decided_by,
            decided_at=now_utc,
        )
    )
    result = await db.execute(stmt)
    await db.commit()

    if result.rowcount == 0:
        # Check if record exists to distinguish 404 from 409
        rec = await db.get(Approval, approval_id)
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approval request {approval_id} not found.",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Approval request {approval_id} has already been resolved with status '{rec.status}'.",
        )

    # 2. Fetch updated record for resumption
    rec = await db.get(Approval, approval_id)

    # 3. Resume LangGraph Agent Workflow
    try:
        agent_res = await resume_agent_workflow(
            run_id=rec.run_id,
            approval_id=approval_id,
            decision="APPROVED",
            decided_by=decided_by,
            session=db,
        )
        return ApprovalActionResponse(
            approval_id=approval_id,
            status=ApprovalStatus.APPROVED,
            message=f"Action '{rec.tool_name}' approved and executed successfully.",
            agent_run_id=rec.run_id,
            agent_status=agent_res.status,
            final_answer=agent_res.final_answer,
        )
    except Exception as e:
        logger.error(f"Failed to resume workflow after approval: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Approval recorded, but resuming agent workflow failed: {str(e)}",
        )


@router.post("/{approval_id}/reject", response_model=ApprovalActionResponse, status_code=status.HTTP_200_OK)
async def reject_request(
    approval_id: uuid.UUID,
    request: ApprovalRejectRequest,
    db: AsyncSession = Depends(get_db),
) -> ApprovalActionResponse:
    """
    Reject a pending sensitive tool invocation.
    Atomically transitions status to REJECTED using compare-and-set semantics.
    """
    now_utc = datetime.now(timezone.utc)
    
    # 1. Atomic Compare-And-Set: UPDATE ... WHERE id = :id AND status = 'PENDING'
    stmt = (
        update(Approval)
        .where(Approval.id == approval_id, Approval.status == "PENDING")
        .values(
            status="REJECTED",
            decided_by=request.decided_by,
            decided_at=now_utc,
            rejection_reason=request.rejection_reason,
        )
    )
    result = await db.execute(stmt)
    await db.commit()

    if result.rowcount == 0:
        rec = await db.get(Approval, approval_id)
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approval request {approval_id} not found.",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Approval request {approval_id} has already been resolved with status '{rec.status}'.",
        )

    rec = await db.get(Approval, approval_id)

    # 3. Resume LangGraph Agent Workflow with safe rejection observation
    try:
        agent_res = await resume_agent_workflow(
            run_id=rec.run_id,
            approval_id=approval_id,
            decision="REJECTED",
            decided_by=request.decided_by,
            rejection_reason=request.rejection_reason,
            session=db,
        )
        return ApprovalActionResponse(
            approval_id=approval_id,
            status=ApprovalStatus.REJECTED,
            message=f"Action '{rec.tool_name}' rejected. Safe final synthesis generated.",
            agent_run_id=rec.run_id,
            agent_status=agent_res.status,
            final_answer=agent_res.final_answer,
        )
    except Exception as e:
        logger.error(f"Failed to resume workflow after rejection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rejection recorded, but resuming agent workflow failed: {str(e)}",
        )
