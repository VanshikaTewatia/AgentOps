from typing import Dict, Any, List
from app.agents.state import AgentState
from app.core.llm import get_llm_client
from app.core.logging import get_logger
from app.schemas.agent import Plan, PlanStep, DelegationPlan, SpecialistTask

logger = get_logger(__name__)


async def planner_node(state: AgentState) -> Dict[str, Any]:
    """
    Supervisor Planner Node: Deconstructs user request into specialized agent tasks
    (DelegationPlan) while preserving structured Plan compatibility.
    """
    user_request = state.get("user_request", "")
    logger.info(f"Supervisor Planner creating dynamic delegation plan for: '{user_request[:100]}'")

    llm_client = get_llm_client()

    messages = [
        {
            "role": "system",
            "content": (
                "You are the Supervisor Planning Agent for AGENTOPS. "
                "Analyze the user's technical operations request and dynamically determine "
                "which specialized agents are required:\n"
                "- DiagnosticAgent: Inspect service health, metrics, active incidents, telemetry.\n"
                "- KnowledgeAgent: Search operational runbooks and documentation via RAG.\n"
                "- IncidentAgent: Incident triage, history correlation, adding comments, or ticket creation.\n"
                "Only delegate tasks to specialists that are strictly necessary."
            ),
        },
        {"role": "user", "content": user_request},
    ]

    # 1. Generate multi-agent DelegationPlan
    try:
        delegation_plan: DelegationPlan = await llm_client.generate_structured(
            messages=messages,
            response_model=DelegationPlan,
        )
    except Exception as e:
        logger.error(f"Supervisor failed to generate delegation plan: {e}")
        delegation_plan = DelegationPlan(
            plan_summary=f"Direct investigation for: {user_request[:60]}",
            tasks=[
                SpecialistTask(
                    target_agent="KnowledgeAgent",
                    task_description=f"Retrieve operational documentation for: {user_request[:60]}",
                    required_tools=["search_knowledge_base"],
                )
            ],
            estimated_impact="LOW",
        )

    # 2. Build backward-compatible Plan for UI/API
    plan_steps: List[PlanStep] = []
    for idx, t in enumerate(delegation_plan.tasks, 1):
        req_tool = t.required_tools[0] if t.required_tools else None
        is_approval = req_tool in ("create_incident", "add_incident_comment")
        plan_steps.append(
            PlanStep(
                step_number=idx,
                description=f"[{t.target_agent}] {t.task_description}",
                tool_required=req_tool,
                requires_rag=(t.target_agent == "KnowledgeAgent"),
                requires_human_approval=is_approval,
                status="PENDING",
            )
        )

    plan = Plan(
        task_summary=delegation_plan.plan_summary,
        steps=plan_steps,
        estimated_impact=delegation_plan.estimated_impact,
    )

    tasks_dicts = [t.model_dump() for t in delegation_plan.tasks]
    agents_involved = list(dict.fromkeys(["SupervisorAgent"] + [t.target_agent for t in delegation_plan.tasks]))

    logger.info(
        f"Supervisor dynamically delegated {len(tasks_dicts)} task(s) to agents: {agents_involved}. "
        f"Summary: {delegation_plan.plan_summary}"
    )

    return {
        "plan": plan,
        "delegated_tasks": tasks_dicts,
        "current_task_index": 0,
        "current_step_index": 0,
        "agents_used": agents_involved,
        "iteration_count": state.get("iteration_count", 0) + 1,
    }
