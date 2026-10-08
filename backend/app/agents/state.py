from typing import Any, Dict, List, Optional, TypedDict
from app.schemas.agent import (
    Plan,
    EvidenceItem,
    ToolCallData,
    ToolResultData,
    ApprovalRequest,
    ApprovalResult,
)
from app.schemas.rag import RAGSource


class AgentState(TypedDict, total=False):
    """Strongly typed LangGraph state representing complete multi-agent operational context."""
    user_request: str
    conversation_id: str
    run_id: str
    plan: Optional[Plan]
    current_step_index: int
    messages: List[Dict[str, Any]]
    
    # Multi-Agent Delegation State
    active_agent: Optional[str]  # e.g. "SupervisorAgent", "DiagnosticAgent", etc.
    delegated_tasks: List[Dict[str, Any]]
    current_task_index: int
    agent_results: List[Dict[str, Any]]
    agents_used: List[str]
    delegation_history: List[str]
    conflicting_evidence: List[Dict[str, Any]]
    
    # Tool Calling State
    available_tools: List[str]
    requested_tool_calls: List[ToolCallData]
    completed_tool_calls: List[ToolResultData]
    tool_calls: List[ToolCallData]
    tool_results: List[ToolResultData]
    tool_iteration: int
    
    # Human-in-the-Loop & Approval State
    pending_approval: Optional[ApprovalRequest]
    approval_id: Optional[str]
    pending_tool_name: Optional[str]
    pending_tool_arguments: Optional[Dict[str, Any]]
    approval_status: Optional[str]  # "PENDING", "APPROVED", "REJECTED"
    resume_required: bool
    approved_by: Optional[str]
    rejection_reason: Optional[str]
    
    retrieved_documents: List[RAGSource]
    evidence: List[EvidenceItem]
    errors: List[str]
    execution_errors: List[str]
    final_answer: Optional[str]
    execution_status: str  # "RUNNING", "WAITING_APPROVAL", "COMPLETED", "FAILED"
    iteration_count: int
    total_tokens: int


def create_initial_state(
    user_request: str,
    conversation_id: str,
    run_id: str,
) -> AgentState:
    """Factory helper to construct clean initial AgentState."""
    return {
        "user_request": user_request,
        "conversation_id": conversation_id,
        "run_id": run_id,
        "plan": None,
        "current_step_index": 0,
        "messages": [{"role": "user", "content": user_request}],
        "active_agent": "SupervisorAgent",
        "delegated_tasks": [],
        "current_task_index": 0,
        "agent_results": [],
        "agents_used": ["SupervisorAgent"],
        "delegation_history": [],
        "conflicting_evidence": [],
        "available_tools": [],
        "requested_tool_calls": [],
        "completed_tool_calls": [],
        "tool_calls": [],
        "tool_results": [],
        "tool_iteration": 0,
        "pending_approval": None,
        "approval_id": None,
        "pending_tool_name": None,
        "pending_tool_arguments": None,
        "approval_status": None,
        "resume_required": False,
        "approved_by": None,
        "rejection_reason": None,
        "retrieved_documents": [],
        "evidence": [],
        "errors": [],
        "execution_errors": [],
        "final_answer": None,
        "execution_status": "RUNNING",
        "iteration_count": 0,
        "total_tokens": 0,
    }
