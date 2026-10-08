import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class EvaluationCaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    case_id: str
    category: str
    user_query: str
    expected_agents: List[str] = Field(default_factory=list)
    expected_tools: List[str] = Field(default_factory=list)
    expected_evidence_types: List[str] = Field(default_factory=list)
    expected_answer_properties: List[str] = Field(default_factory=list)
    requires_approval: bool = False
    expected_final_state: str = "COMPLETED"


class EvaluationCaseResultSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    case_id: str
    category: str
    query: str
    status: str  # "PASSED" or "FAILED"
    actual_agents: List[str] = Field(default_factory=list)
    expected_agents: List[str] = Field(default_factory=list)
    actual_tools: List[str] = Field(default_factory=list)
    expected_tools: List[str] = Field(default_factory=list)
    routing_correct: bool = True
    tool_selection_correct: bool = True
    grounded: bool = True
    provenance_valid: bool = True
    approval_safety_passed: bool = True
    conflict_handled: bool = True
    evidence_count: int = 0
    latency_ms: float = 0.0
    tokens_used: int = 0
    details: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class EvaluationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_name: str
    model_provider: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    routing_accuracy: float
    tool_selection_accuracy: float
    grounding_rate: float
    provenance_rate: float
    conflict_detection_rate: float
    approval_safety_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    total_tokens: int
    estimated_cost_usd: float
    metrics: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    results: Optional[List[EvaluationCaseResultSchema]] = None


class EvaluationTriggerRequest(BaseModel):
    dataset_name: Optional[str] = "agentops-eval-v1"
    max_cases: Optional[int] = None
