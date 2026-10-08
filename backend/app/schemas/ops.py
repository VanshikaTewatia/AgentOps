import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    status: str
    owner_team: str
    repository_url: Optional[str] = None
    metadata_info: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    service_id: uuid.UUID
    service_name: Optional[str] = None
    title: str
    description: str
    severity: str
    status: str
    root_cause: Optional[str] = None
    resolution_notes: Optional[str] = None
    comments: Optional[List[Any]] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
