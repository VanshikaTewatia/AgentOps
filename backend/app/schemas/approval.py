import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ApprovalDecisionRequest(BaseModel):
    decided_by: str = Field(default="SRE-Lead", description="Username or ID of the human approver")
    reason: Optional[str] = Field(None, description="Optional notes or context for the decision")


class ApprovalRejectRequest(BaseModel):
    decided_by: str = Field(default="SRE-Lead", description="Username or ID of the human rejecter")
    rejection_reason: str = Field(..., min_length=2, description="Explanation why the requested action was rejected")


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    tool_name: str
    tool_args: Dict[str, Any]
    reason: str
    status: ApprovalStatus
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ApprovalActionResponse(BaseModel):
    approval_id: uuid.UUID
    status: ApprovalStatus
    message: str
    agent_run_id: uuid.UUID
    agent_status: str
    final_answer: Optional[str] = None
