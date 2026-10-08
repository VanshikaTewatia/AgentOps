import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.service import Service
from app.schemas.ops import ServiceResponse

router = APIRouter()


@router.get("", response_model=List[ServiceResponse], status_code=status.HTTP_200_OK)
async def list_services(
    db: AsyncSession = Depends(get_db),
) -> List[ServiceResponse]:
    """List all registered microservices and infrastructure components."""
    result = await db.execute(select(Service).order_by(Service.name.asc()))
    services = result.scalars().all()
    return [ServiceResponse.model_validate(s) for s in services]


@router.get("/{service_id}", response_model=ServiceResponse, status_code=status.HTTP_200_OK)
async def get_service(
    service_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ServiceResponse:
    """Retrieve details of a single service."""
    svc = await db.get(Service, service_id)
    if not svc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service with ID {service_id} not found.",
        )
    return ServiceResponse.model_validate(svc)
