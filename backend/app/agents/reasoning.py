from typing import Any, Dict, List
from app.agents.state import AgentState
from app.core.llm import get_llm_client
from app.core.logging import get_logger
from app.schemas.agent import ToolCallData
from app.tools import get_default_tool_registry

logger = get_logger(__name__)


async def reasoning_node(state: AgentState) -> Dict[str, Any]:
    """
    Reasoning Node: Inspects current plan step, observations, and tool history
    to decide which tool to call or proceed to next action.
    """
    user_request = state.get("user_request", "")
    plan = state.get("plan")
    step_idx = state.get("current_step_index", 0)
    tool_results = state.get("tool_results", [])
    
    registry = get_default_tool_registry()
    tools_definitions = registry.get_definitions()
    
    # Check if there is an active step requiring a tool
    tool_to_call: List[ToolCallData] = []
    
    if plan and step_idx < len(plan.steps):
        step = plan.steps[step_idx]
        logger.info(f"Reasoning node evaluating step {step.step_number}: '{step.description}' (tool: {step.tool_required})")
        
        if step.tool_required:
            llm_client = get_llm_client()
            context_messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an SRE reasoning agent. Given the user problem, plan, and current step, "
                        "select the appropriate tool and generate valid arguments."
                    ),
                },
                {"role": "user", "content": f"{user_request}\nCurrent step: {step.description}\nTool required: {step.tool_required}"},
            ]
            
            tool_to_call = await llm_client.decide_tool_calls(
                messages=context_messages,
                tools_definitions=tools_definitions,
            )
            
            # Fallback direct call if LLM returned empty list but step specifies tool
            if not tool_to_call and registry.get(step.tool_required):
                # Deterministic fallback args
                svc = "payment-service" if "payment" in user_request.lower() else "kafka" if "kafka" in user_request.lower() else "redis" if "redis" in user_request.lower() else "infrastructure"
                args: Dict[str, Any] = {}
                if step.tool_required in ("get_service_status", "get_service_metrics"):
                    args = {"service": svc}
                elif step.tool_required == "query_incidents":
                    args = {"service": svc}
                elif step.tool_required == "search_knowledge_base":
                    args = {"query": user_request[:80]}
                elif step.tool_required == "create_incident":
                    args = {"title": user_request[:60], "description": user_request, "severity": "HIGH"}
                
                tool_to_call = [
                    ToolCallData(
                        tool_name=step.tool_required,
                        tool_args=args,
                    )
                ]

    return {
        "requested_tool_calls": tool_to_call,
        "available_tools": registry.list_available(),
    }
