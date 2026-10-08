from typing import Any, Dict, Literal
from app.agents.state import AgentState
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

MAX_DELEGATIONS = 8


async def orchestrator_node(state: AgentState) -> Dict[str, Any]:
    """
    Supervisor/Orchestrator node: Evaluates workflow progress and enforces guardrails
    across multi-agent delegation and single-agent plan steps.
    """
    iteration = state.get("iteration_count", 0) + 1
    tool_iter = state.get("tool_iteration", 0)
    plan = state.get("plan")
    delegated_tasks = state.get("delegated_tasks", [])
    current_task_idx = state.get("current_task_index", 0)
    current_step_idx = state.get("current_step_index", 0)
    errors = state.get("errors", [])
    execution_status = state.get("execution_status", "RUNNING")
    is_resumed = state.get("resume_required", False)
    delegation_hist = state.get("delegation_history", [])

    logger.info(
        f"Supervisor evaluating: iteration={iteration}/{settings.MAX_AGENT_ITERATIONS}, "
        f"tool_iteration={tool_iter}/{settings.MAX_TOOL_ITERATIONS}, "
        f"delegations={len(delegated_tasks)}, task_index={current_task_idx}, "
        f"status={execution_status}, is_resumed={is_resumed}"
    )

    # 1. Guardrail: WAITING_APPROVAL immediately halts workflow for human review
    if execution_status == "WAITING_APPROVAL" and not is_resumed:
        logger.info("Workflow paused in WAITING_APPROVAL state.")
        return {
            "iteration_count": iteration,
            "execution_status": "WAITING_APPROVAL",
        }

    # 2. Guardrail: Max iterations limit prevents runaway workflows
    if iteration > settings.MAX_AGENT_ITERATIONS:
        logger.warning(
            f"Exceeded maximum agent iterations ({settings.MAX_AGENT_ITERATIONS}). Terminating workflow."
        )
        return {
            "iteration_count": iteration,
            "execution_status": "COMPLETED",
            "errors": errors + [f"Workflow reached maximum iterations ({settings.MAX_AGENT_ITERATIONS})"],
        }

    # 3. Guardrail: Max tool iterations limit
    if tool_iter >= settings.MAX_TOOL_ITERATIONS:
        logger.warning(
            f"Exceeded maximum tool iterations ({settings.MAX_TOOL_ITERATIONS}). Terminating tool calls."
        )
        return {
            "iteration_count": iteration,
            "execution_status": "COMPLETED",
            "errors": errors + [f"Workflow reached maximum tool iterations ({settings.MAX_TOOL_ITERATIONS})"],
        }

    # 4. Guardrail: Multi-agent delegation limit
    if len(delegated_tasks) > MAX_DELEGATIONS:
        logger.warning(f"Exceeded maximum specialist delegations ({MAX_DELEGATIONS}). Finalizing.")
        return {
            "iteration_count": iteration,
            "execution_status": "COMPLETED",
            "errors": errors + [f"Supervisor reached maximum delegations ({MAX_DELEGATIONS})"],
        }

    # 5. Resumed execution - proceed directly
    if is_resumed:
        return {
            "iteration_count": iteration,
            "execution_status": "RUNNING",
        }

    # 6. Planning phase: no plan or delegation yet → dispatch to planner / supervisor planner
    if plan is None and not delegated_tasks:
        return {
            "iteration_count": iteration,
            "execution_status": "RUNNING",
        }

    # 7. Check if multi-agent tasks are all completed
    if delegated_tasks and current_task_idx >= len(delegated_tasks):
        logger.info("All delegated specialist tasks completed. Proceeding to analysis/synthesis.")
        return {
            "iteration_count": iteration,
            "execution_status": "COMPLETED",
        }

    # 8. Single-agent plan steps completed
    if plan and not delegated_tasks and current_step_idx >= len(plan.steps):
        logger.info("All plan steps completed. Proceeding to analysis then synthesis.")
        return {
            "iteration_count": iteration,
            "execution_status": "COMPLETED",
        }

    return {
        "iteration_count": iteration,
        "execution_status": "RUNNING",
    }


def route_next_step(
    state: AgentState,
) -> Literal[
    "planner",
    "reasoning",
    "tool_execution",
    "rag_node",
    "analysis",
    "synthesizer",
    "specialist_delegate",
    "__end__",
]:
    """
    Conditional router determining the next LangGraph node to invoke.
    Dynamically routes between supervisor planning, specialist delegations,
    tool execution, RAG, analysis, and synthesis.
    """
    status = state.get("execution_status", "RUNNING")
    iteration = state.get("iteration_count", 0)
    tool_iter = state.get("tool_iteration", 0)
    plan = state.get("plan")
    delegated_tasks = state.get("delegated_tasks", [])
    current_task_idx = state.get("current_task_index", 0)
    current_step_idx = state.get("current_step_index", 0)
    evidence = state.get("evidence", [])
    requested_tools = state.get("requested_tool_calls", [])
    is_resumed = state.get("resume_required", False)

    # If in approval state and not resumed, route to synthesizer to generate clean pending response
    if status == "WAITING_APPROVAL" and not is_resumed:
        return "synthesizer"

    # If workflow is resumed from approval/rejection, route directly to tool_execution to execute/skip tool
    if is_resumed:
        return "tool_execution"

    # Safety valves
    if iteration >= settings.MAX_AGENT_ITERATIONS or tool_iter >= settings.MAX_TOOL_ITERATIONS:
        return "synthesizer"

    if status == "FAILED":
        return "synthesizer"

    # No plan and no delegated tasks yet → must plan first
    if plan is None and not delegated_tasks:
        return "planner"

    # If multi-agent delegation active and tasks remaining
    if delegated_tasks and current_task_idx < len(delegated_tasks):
        return "specialist_delegate"

    # If tools were decided by reasoning node, route to tool_execution
    if requested_tools:
        return "tool_execution"

    # All multi-agent tasks or plan steps done → run analysis if unclassified evidence exists, else synthesize
    has_tasks_remaining = (
        (delegated_tasks and current_task_idx < len(delegated_tasks))
        or (plan and not delegated_tasks and current_step_idx < len(plan.steps))
    )

    if not has_tasks_remaining:
        has_unclassified = any(
            "[FACT]" not in e.content
            and "[INFERENCE]" not in e.content
            and "[DOCUMENTATION]" not in e.content
            and "[OBSERVATION]" not in e.content
            for e in evidence
        )
        if evidence and has_unclassified:
            return "analysis"
        return "synthesizer"

    # Single-agent fallback: Step is in-progress → check step requirements
    if plan and not delegated_tasks and current_step_idx < len(plan.steps):
        step = plan.steps[current_step_idx]
        if step.tool_required:
            return "reasoning"
        elif step.requires_rag:
            return "rag_node"

    return "reasoning"
