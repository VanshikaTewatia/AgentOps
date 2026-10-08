from typing import Any, Dict, List
from app.agents.state import AgentState
from app.core.llm import get_llm_client
from app.core.logging import get_logger

logger = get_logger(__name__)


async def synthesizer_node(state: AgentState) -> Dict[str, Any]:
    """
    Synthesis Agent Node: Aggregates evidence from specialist agents, resolves conflicts,
    distinguishes FACT from INFERENCE, attributes provenance, and produces grounded final summary.
    """
    user_request = state.get("user_request", "")
    plan = state.get("plan")
    retrieved_docs = state.get("retrieved_documents", [])
    evidence = state.get("evidence", [])
    errors = state.get("errors", [])
    execution_errors = state.get("execution_errors", [])
    tool_results = state.get("tool_results", [])
    pending_approval = state.get("pending_approval")
    execution_status = state.get("execution_status", "COMPLETED")
    agents_used = state.get("agents_used", ["SupervisorAgent"])
    conflicts = state.get("conflicting_evidence", [])
    agent_results = state.get("agent_results", [])

    logger.info(f"Synthesizer formulating response for request: '{user_request[:100]}', status: {execution_status}")

    # If pending approval, produce clear human approval notice
    if execution_status == "WAITING_APPROVAL" and pending_approval:
        return {
            "final_answer": (
                f"### Operational Action Intercepted (Human Approval Required)\n\n"
                f"The agent generated a sensitive write operation requiring authorization:\n"
                f"- **Tool**: `{pending_approval.tool_name}`\n"
                f"- **Action**: {pending_approval.reason}\n"
                f"- **Parameters**: `{pending_approval.tool_args}`\n"
                f"- **Approval ID**: `{pending_approval.approval_id}`\n\n"
                f"Execution has been paused safely in state `WAITING_APPROVAL`. "
                f"A human operator must approve this action before changes are committed."
            ),
            "execution_status": "WAITING_APPROVAL",
        }

    llm_client = get_llm_client()

    # 1. Structure Provenance & Evidence by Class
    facts: List[str] = []
    inferences: List[str] = []
    doc_refs: List[str] = []

    for ev in evidence:
        origin = f"[{ev.originating_agent}]" if ev.originating_agent else ""
        source_label = f"({ev.source_identifier})"
        if ev.evidence_class == "FACT" or "[FACT]" in ev.content:
            facts.append(f"- {origin} {source_label}: {ev.content.replace('[FACT]', '').strip()}")
        elif ev.evidence_class == "DOCUMENTATION" or "[DOCUMENTATION]" in ev.content:
            doc_refs.append(f"- {origin} {source_label}: {ev.content.replace('[DOCUMENTATION]', '').strip()}")
        else:
            inferences.append(f"- {origin} {source_label}: {ev.content.replace('[INFERENCE]', '').strip()}")

    # 2. Build synthesis sections
    sections: List[str] = []
    
    sections.append(f"## Multi-Agent Investigation Summary\n")
    sections.append(f"**Inquiry**: {user_request}\n")
    sections.append(f"**Specialists Involved**: {', '.join(agents_used)}\n")

    if facts:
        sections.append("### Confirmed Facts & Telemetry Observations:")
        sections.extend(facts[:6])

    if doc_refs:
        sections.append("\n### Documented Runbook Procedures:")
        sections.extend(doc_refs[:4])

    if inferences:
        sections.append("\n### Analytical Inferences & Hypotheses:")
        sections.extend(inferences[:4])

    if conflicts:
        sections.append("\n### [WARNING] Conflicting Evidence & Ambiguity Notice:")
        for c in conflicts:
            sections.append(
                f"- **{c.get('topic')}**: {c.get('description')}\n"
                f"  * Evidence A: {c.get('item_a', {}).get('content')}\n"
                f"  * Evidence B: {c.get('item_b', {}).get('content')}\n"
                f"  * *Recommendation*: Exercising uncertainty; fresher real-time telemetry is preferred."
            )

    all_errors = errors + execution_errors
    if all_errors:
        sections.append("\n### Execution Warnings / Partial Failures:")
        for err in set(all_errors):
            sections.append(f"- {err}")

    # Build Provenance Section
    sections.append("\n### Evidence Provenance & Attribution:")
    sections.append(
        f"- Total Evidence Items: {len(evidence)}\n"
        f"- Diagnostic Tools Executed: {len(tool_results)}\n"
        f"- Specialists Executed: {len(agent_results)}"
    )

    final_grounded_answer = "\n".join(sections)

    return {
        "final_answer": final_grounded_answer,
        "execution_status": "COMPLETED",
    }
