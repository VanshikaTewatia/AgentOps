import uuid
from typing import Any, List, Optional
from sqlalchemy import String, Text, Integer, Float, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, TimestampMixin


class EvaluationRun(Base, TimestampMixin):
    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False, default="agentops-eval-v1")
    model_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="mock")
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Aggregated quality scores (0.0 to 1.0)
    routing_accuracy: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tool_selection_accuracy: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    grounding_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    provenance_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    conflict_detection_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    approval_safety_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    
    # Latency & token metrics
    avg_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    p95_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    
    metrics: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    results: Mapped[List["EvaluationCaseResult"]] = relationship(
        "EvaluationCaseResult",
        back_populates="evaluation_run",
        cascade="all, delete-orphan",
        order_by="EvaluationCaseResult.created_at",
    )


class EvaluationCaseResult(Base, TimestampMixin):
    __tablename__ = "evaluation_case_results"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    case_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # PASSED, FAILED
    
    actual_agents: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    expected_agents: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    actual_tools: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    expected_tools: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    
    routing_correct: Mapped[bool] = mapped_column(nullable=False, default=True)
    tool_selection_correct: Mapped[bool] = mapped_column(nullable=False, default=True)
    grounded: Mapped[bool] = mapped_column(nullable=False, default=True)
    provenance_valid: Mapped[bool] = mapped_column(nullable=False, default=True)
    approval_safety_passed: Mapped[bool] = mapped_column(nullable=False, default=True)
    conflict_handled: Mapped[bool] = mapped_column(nullable=False, default=True)
    
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    details: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    evaluation_run: Mapped["EvaluationRun"] = relationship("EvaluationRun", back_populates="results")
