"""
Analysis Node — Phase 3 LangGraph Agent.

Sits between the RAG node and the synthesizer.  For each piece of retrieved
evidence it decides whether the content is a *confirmed fact* (directly stated
in a retrieved document) or an *inference* (a conclusion the agent is drawing
from the evidence).  This explicit distinction is required for interview-quality
explainability and for grounding the final answer honestly.
"""

import uuid
from typing import Any, Dict, List

from app.agents.state import AgentState
from app.core.llm import get_llm_client
from app.core.logging import get_logger
from app.schemas.agent import EvidenceItem

logger = get_logger(__name__)


def _detect_conflicts(evidence: List[EvidenceItem]) -> List[Dict[str, Any]]:
    """
    Identifies conflicting factual observations or contradictory statements across evidence items.
    Example: 'lag is increasing' vs 'lag is stable' or 'healthy' vs 'unhealthy'.
    """
    conflicts: List[Dict[str, Any]] = []
    
    # Check for direct antonym/contradiction patterns in collected items
    for i, item1 in enumerate(evidence):
        c1 = item1.content.lower()
        for j, item2 in enumerate(evidence[i + 1:], i + 1):
            c2 = item2.content.lower()
            
            # Pattern 1: Increasing vs Stable/Decreasing
            if ("increasing" in c1 or "spike" in c1) and ("stable" in c2 or "normal" in c2 or "decreasing" in c2):
                conflicts.append({
                    "conflict_id": f"conf-{uuid.uuid4().hex[:6]}",
                    "topic": "Trend Contradiction",
                    "item_a": {"agent": item1.originating_agent, "source": item1.source_identifier, "content": item1.content},
                    "item_b": {"agent": item2.originating_agent, "source": item2.source_identifier, "content": item2.content},
                    "description": f"Contradiction between '{item1.source_identifier}' ({item1.originating_agent}) and '{item2.source_identifier}' ({item2.originating_agent})",
                })
            # Pattern 2: Healthy vs Unhealthy/Degraded/Critical
            elif ("healthy" in c1 or "operational" in c1) and ("degraded" in c2 or "critical" in c2 or "exhaustion" in c2):
                conflicts.append({
                    "conflict_id": f"conf-{uuid.uuid4().hex[:6]}",
                    "topic": "Status Contradiction",
                    "item_a": {"agent": item1.originating_agent, "source": item1.source_identifier, "content": item1.content},
                    "item_b": {"agent": item2.originating_agent, "source": item2.source_identifier, "content": item2.content},
                    "description": f"Status mismatch: '{item1.content[:80]}' vs '{item2.content[:80]}'",
                })
    return conflicts


def _classify_evidence(
    item: EvidenceItem,
    user_request: str,
) -> EvidenceItem:
    """
    Deterministically classify an evidence item as FACT, DOCUMENTATION, or INFERENCE.
    """
    # If already classified with clean metadata, preserve
    if item.evidence_class in ("FACT", "DOCUMENTATION", "INFERENCE", "OBSERVATION"):
        prefix = f"[{item.evidence_class}] " if f"[{item.evidence_class}]" not in item.content else ""
        return EvidenceItem(
            evidence_id=item.evidence_id,
            source_type=item.source_type,
            source_identifier=item.source_identifier,
            source_id=item.source_id,
            source_description=item.source_description,
            originating_agent=item.originating_agent,
            content=f"{prefix}{item.content}" if prefix else item.content,
            evidence_class=item.evidence_class,
            confidence=item.confidence,
            timestamp=item.timestamp,
        )

    if item.source_type == "RAG_CHUNK" and item.confidence >= 0.85:
        return EvidenceItem(
            evidence_id=item.evidence_id,
            source_type=item.source_type,
            source_identifier=item.source_identifier,
            source_id=item.source_id,
            source_description=item.source_description,
            originating_agent=item.originating_agent or "KnowledgeAgent",
            content=f"[DOCUMENTATION] {item.content}",
            evidence_class="DOCUMENTATION",
            confidence=item.confidence,
            timestamp=item.timestamp,
        )
    elif item.source_type == "RAG_CHUNK":
        return EvidenceItem(
            evidence_id=item.evidence_id,
            source_type=item.source_type,
            source_identifier=item.source_identifier,
            source_id=item.source_id,
            source_description=item.source_description,
            originating_agent=item.originating_agent or "KnowledgeAgent",
            content=f"[INFERENCE] Based on retrieved documentation: {item.content}",
            evidence_class="INFERENCE",
            confidence=max(0.0, item.confidence - 0.1),
            timestamp=item.timestamp,
        )
    else:
        return EvidenceItem(
            evidence_id=item.evidence_id,
            source_type=item.source_type,
            source_identifier=item.source_identifier,
            source_id=item.source_id,
            source_description=item.source_description,
            originating_agent=item.originating_agent or "DiagnosticAgent",
            content=f"[FACT] {item.content}",
            evidence_class="FACT",
            confidence=item.confidence,
            timestamp=item.timestamp,
        )


async def analysis_node(state: AgentState) -> Dict[str, Any]:
    """
    Analysis Agent node: Reviews aggregated evidence from all specialist agents,
    classifies FACT vs INFERENCE vs DOCUMENTATION, and identifies conflicting evidence.
    """
    user_request = state.get("user_request", "")
    evidence: List[EvidenceItem] = list(state.get("evidence", []))
    retrieved_docs = state.get("retrieved_documents", [])
    errors: List[str] = list(state.get("errors", []))

    logger.info(
        f"Analysis node processing {len(evidence)} evidence items "
        f"from {len(retrieved_docs)} retrieved documents."
    )

    if not evidence:
        logger.warning("Analysis node received no evidence items to process.")
        errors.append("Analysis node: no evidence available; proceeding with empty context.")
        return {"evidence": [], "errors": errors, "conflicting_evidence": []}

    # 1. Classify evidence
    classified: List[EvidenceItem] = [_classify_evidence(item, user_request) for item in evidence]

    # 2. Detect conflicting evidence
    conflicts = _detect_conflicts(classified)
    if conflicts:
        logger.warning(f"Analysis node detected {len(conflicts)} evidence conflict(s).")

    fact_count = sum(1 for e in classified if e.evidence_class == "FACT" or "[FACT]" in e.content)
    doc_count = sum(1 for e in classified if e.evidence_class == "DOCUMENTATION" or "[DOCUMENTATION]" in e.content)
    inference_count = len(classified) - fact_count - doc_count

    logger.info(
        f"Analysis complete: {fact_count} facts, {doc_count} documentation, "
        f"{inference_count} inferences, {len(conflicts)} conflicts from {len(classified)} items."
    )

    return {
        "evidence": classified,
        "conflicting_evidence": conflicts,
        "errors": errors,
    }
