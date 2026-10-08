import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.incident import Incident
from app.models.service import Service
from app.schemas.ops import IncidentResponse

router = APIRouter()


@router.get("", response_model=List[IncidentResponse], status_code=status.HTTP_200_OK)
async def list_incidents(
    service_id: Optional[uuid.UUID] = None,
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> List[IncidentResponse]:
    """List operational incident tickets with service metadata."""
    stmt = (
        select(Incident)
        .options(selectinload(Incident.service))
        .order_by(Incident.created_at.desc())
    )
    if service_id:
        stmt = stmt.where(Incident.service_id == service_id)
    if status_filter:
        stmt = stmt.where(Incident.status == status_filter.upper())

    result = await db.execute(stmt)
    incidents = result.scalars().all()

    return [
        IncidentResponse(
            id=inc.id,
            service_id=inc.service_id,
            service_name=inc.service.name if inc.service else None,
            title=inc.title,
            description=inc.description,
            severity=inc.severity,
            status=inc.status,
            root_cause=inc.root_cause,
            resolution_notes=inc.resolution_notes,
            comments=inc.comments or [],
            resolved_at=inc.resolved_at,
            created_at=inc.created_at,
            updated_at=inc.updated_at,
        )
        for inc in incidents
    ]


@router.get("/{incident_id}", response_model=IncidentResponse, status_code=status.HTTP_200_OK)
async def get_incident(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> IncidentResponse:
    """Retrieve details of a single incident ticket."""
    result = await db.execute(
        select(Incident)
        .options(selectinload(Incident.service))
        .where(Incident.id == incident_id)
    )
    inc = result.scalar_one_or_none()
    if not inc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found.",
        )
    return IncidentResponse(
        id=inc.id,
        service_id=inc.service_id,
        service_name=inc.service.name if inc.service else None,
        title=inc.title,
        description=inc.description,
        severity=inc.severity,
        status=inc.status,
        root_cause=inc.root_cause,
        resolution_notes=inc.resolution_notes,
        comments=inc.comments or [],
        resolved_at=inc.resolved_at,
        created_at=inc.created_at,
        updated_at=inc.updated_at,
    )
