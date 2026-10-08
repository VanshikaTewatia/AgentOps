import uuid
from typing import Any, List, Optional
from sqlalchemy import String, Text, Integer, Float, ForeignKey, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, TimestampMixin


class AgentRun(Base, TimestampMixin):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    user_request: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="RUNNING", index=True
    )  # RUNNING, WAITING_APPROVAL, COMPLETED, FAILED
    plan: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    final_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    meta_info: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    events: Mapped[List["AgentEvent"]] = relationship(
        "AgentEvent", back_populates="agent_run", cascade="all, delete-orphan", order_by="AgentEvent.created_at"
    )
    tool_executions: Mapped[List["ToolExecution"]] = relationship(
        "ToolExecution", back_populates="agent_run", cascade="all, delete-orphan", order_by="ToolExecution.created_at"
    )


class AgentEvent(Base, TimestampMixin):
    __tablename__ = "agent_events"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # NODE_START, NODE_END, ERROR, APPROVAL_REQUESTED
    payload: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    agent_run: Mapped["AgentRun"] = relationship("AgentRun", back_populates="events")


class ToolExecution(Base, TimestampMixin):
    __tablename__ = "tool_executions"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tool_input: Mapped[dict] = mapped_column(JSON, nullable=False)
    tool_output: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="SUCCESS"
    )  # SUCCESS, FAILED, PENDING_APPROVAL, REJECTED
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    agent_run: Mapped["AgentRun"] = relationship("AgentRun", back_populates="tool_executions")
