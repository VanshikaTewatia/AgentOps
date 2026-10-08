import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.evaluation import EvaluationRun, EvaluationCaseResult
from app.schemas.evaluation import (
    EvaluationRunResponse,
    EvaluationCaseResultSchema,
    EvaluationTriggerRequest,
)
from app.services.evaluation_service import EvaluationRunner

router = APIRouter()


@router.post(
    "/run",
    response_model=EvaluationRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger evaluation benchmark run",
)
async def trigger_evaluation_run(
    request: EvaluationTriggerRequest,
    session: AsyncSession = Depends(get_db),
):
    """Executes the standard evaluation benchmark suite across operational test cases."""
    runner = EvaluationRunner(session)
    try:
        run_response = await runner.run_evaluation(
            dataset_name=request.dataset_name or "agentops-eval-v1",
            max_cases=request.max_cases,
        )
        return run_response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evaluation execution failed: {str(e)}",
        )


@router.get(
    "",
    response_model=List[EvaluationRunResponse],
    summary="List all evaluation runs",
)
async def list_evaluation_runs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """Lists historical evaluation runs ordered by newest first."""
    result = await session.execute(
        select(EvaluationRun)
        .options(selectinload(EvaluationRun.results))
        .order_by(EvaluationRun.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    runs = result.scalars().all()
    return [EvaluationRunResponse.model_validate(r) for r in runs]


@router.get(
    "/{evaluation_id}",
    response_model=EvaluationRunResponse,
    summary="Get single evaluation run details",
)
async def get_evaluation_run(
    evaluation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    """Retrieves full evaluation run details including aggregated quality metrics."""
    result = await session.execute(
        select(EvaluationRun)
        .options(selectinload(EvaluationRun.results))
        .where(EvaluationRun.id == evaluation_id)
    )
    run_rec = result.scalar_one_or_none()
    if not run_rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation run {evaluation_id} not found",
        )
    return EvaluationRunResponse.model_validate(run_rec)


@router.get(
    "/{evaluation_id}/results",
    response_model=List[EvaluationCaseResultSchema],
    summary="Get per-case evaluation results",
)
async def get_evaluation_run_results(
    evaluation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    """Retrieves detailed per-case results for a specific evaluation run."""
    result = await session.execute(
        select(EvaluationCaseResult)
        .where(EvaluationCaseResult.run_id == evaluation_id)
        .order_by(EvaluationCaseResult.created_at.asc())
    )
    case_results = result.scalars().all()
    return [EvaluationCaseResultSchema.model_validate(r) for r in case_results]
