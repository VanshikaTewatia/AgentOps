from datetime import datetime
from typing import Dict, Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., description="Overall system health status (healthy, degraded, unhealth)")
    app_name: str
    environment: str
    database_connected: bool
    version: str = "1.0.0"
    timestamp: datetime
    details: Dict[str, Any] = Field(default_factory=dict)
