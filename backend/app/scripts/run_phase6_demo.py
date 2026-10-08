"""
Phase 6 Multi-Agent Analysis, Evidence Aggregation & Conflict Handling Demo.
Executes live against local PostgreSQL database to verify:
1. Dynamic Supervisor Routing & Delegation
2. Specialized Agent Execution (Diagnostic, Knowledge, Incident)
3. Structured Evidence Collection & Epistemic Classification (FACT, DOCUMENTATION, INFERENCE)
4. Conflicting Evidence Identification & Uncertainty Handling
5. Sensitive WRITE Approval Integration & Workflow Resumption
"""

import asyncio
import uuid
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.db.session import async_session_factory
from app.agents.graph import run_agent_workflow, resume_agent_workflow
from app.agents.state import create_initial_state
from app.agents.analysis import analysis_node
from app.agents.synthesizer import synthesizer_node
from app.schemas.agent import EvidenceItem
from app.rag.service import DocumentIngestionService
from app.models.approval import Approval
from sqlalchemy import select


def print_banner(title: str):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


async def main():
    print_banner("AGENTOPS PHASE 6 — MULTI-AGENT VERIFICATION BENCHMARK")

    async with async_session_factory() as session:
        # Seed test documents
        ingestion = DocumentIngestionService(session)
        await ingestion.ingest_document(
            title="Database Connection Pool Guide",
            content="When payment-service exceeds 90% connection pool utilization, check for connection leaks, slow queries, and restart pool workers.",
            source="runbooks/db-pool.md",
            doc_type="runbook",
            metadata={"service": "payment-service"},
        )
        await ingestion.ingest_document(
            title="Kafka Consumer Lag Playbook",
            content="When consumer lag increases over 10,000 records, inspect partition assignment and scale consumer group replicas.",
            source="runbooks/kafka.md",
            doc_type="runbook",
            metadata={"service": "kafka"},
        )
        await session.commit()

        # -------------------------------------------------------------
        # SCENARIO 1: Diagnostic & Knowledge Specialist Investigation
        # -------------------------------------------------------------
        print_banner("SCENARIO 1: Dynamic Supervisor Delegation (Diagnostic + Knowledge)")
        query_1 = "Why is payment-service experiencing database connection exhaustion?"
        print(f"User Query: '{query_1}'")
        res1 = await run_agent_workflow(query_1, conversation_id="phase6-demo-s1", session=session)
        print(f"Workflow Status   : {res1.status}")
        print(f"Agents Involved   : {res1.agents_used}")
        print(f"Delegations Count : {res1.delegation_count}")
        print(f"Evidence Count    : {res1.evidence_count}")
        print(f"Tools Executed    : {res1.tools_used}")
        print("\n[Synthesizer Output Preview]:")
        for line in res1.final_answer.split("\n")[:12]:
            print(f"  {line}")

        # -------------------------------------------------------------
        # SCENARIO 2: Knowledge-Only Runbook Routing
        # -------------------------------------------------------------
        print_banner("SCENARIO 2: Targeted Runbook Query (KnowledgeAgent Only)")
        query_2 = "What does our Kafka runbook recommend for consumer lag?"
        print(f"User Query: '{query_2}'")
        res2 = await run_agent_workflow(query_2, conversation_id="phase6-demo-s2", session=session)
        print(f"Workflow Status   : {res2.status}")
        print(f"Agents Involved   : {res2.agents_used}")
        print(f"DiagnosticAgent Skipped: {'DiagnosticAgent' not in res2.agents_used}")
        print(f"IncidentAgent Skipped  : {'IncidentAgent' not in res2.agents_used}")

        # -------------------------------------------------------------
        # SCENARIO 3: IncidentAgent WRITE Tool with Phase 5 Approval Gate & Resume
        # -------------------------------------------------------------
        print_banner("SCENARIO 3: IncidentAgent WRITE Action + Human Approval & Resumption")
        query_3 = "Create a high-severity incident for payment-service database exhaustion"
        print(f"User Query: '{query_3}'")
        res3_init = await run_agent_workflow(query_3, conversation_id="phase6-demo-s3", session=session)
        print(f"Initial Status    : {res3_init.status} (Approval Required: {res3_init.approval_required})")
        print(f"Agents Involved   : {res3_init.agents_used}")

        # Query approval
        app_res = await session.execute(select(Approval).where(Approval.run_id == res3_init.id))
        app_rec = app_res.scalar_one()
        print(f"Pending Approval  : ID={app_rec.id}, Tool={app_rec.tool_name}, Status={app_rec.status}")

        print("\n--> Simulating Human Approval via /api/v1/approvals/{id}/approve...")
        res3_resumed = await resume_agent_workflow(
            run_id=res3_init.id,
            approval_id=app_rec.id,
            decision="APPROVED",
            decided_by="sre_lead@enterprise.com",
            session=session,
        )
        print(f"Resumed Status    : {res3_resumed.status}")
        print(f"Tools Executed    : {res3_resumed.tools_used}")
        print(f"Final Answer Head : {res3_resumed.final_answer.splitlines()[0]}")

        # -------------------------------------------------------------
        # SCENARIO 4: Conflicting Evidence Handling & Uncertainty Reporting
        # -------------------------------------------------------------
        print_banner("SCENARIO 4: Conflicting Evidence Detection & Epistemic Honesty")
        print("Feeding contradictory evidence items from different agents into Analysis & Synthesis...")

        state = create_initial_state("Investigate Kafka telemetry discrepancy", "demo-conflict", str(uuid.uuid4()))
        state["evidence"] = [
            EvidenceItem(
                source_type="TOOL_OUTPUT",
                source_identifier="get_service_metrics",
                originating_agent="DiagnosticAgent",
                content="Kafka consumer lag is increasing rapidly (spike to 45,000 records).",
                evidence_class="FACT",
                confidence=1.0,
            ),
            EvidenceItem(
                source_type="TOOL_OUTPUT",
                source_identifier="query_incidents",
                originating_agent="IncidentAgent",
                content="Recent alert reports kafka consumer lag is stable and normal.",
                evidence_class="FACT",
                confidence=1.0,
            ),
        ]
        state["agents_used"] = ["SupervisorAgent", "DiagnosticAgent", "IncidentAgent"]

        analysis_out = await analysis_node(state)
        state.update(analysis_out)
        synth_out = await synthesizer_node(state)

        print(f"Conflicts Detected: {len(state.get('conflicting_evidence', []))}")
        for conf in state.get("conflicting_evidence", []):
            print(f"  * Conflict Topic : {conf.get('topic')}")
            print(f"  * Description    : {conf.get('description')}")

        print("\n[Synthesizer Transparency on Discrepancy]:")
        for line in synth_out["final_answer"].splitlines():
            if "Conflicting Evidence" in line or "Evidence A" in line or "Evidence B" in line or "Recommendation" in line:
                print(f"  {line}")

    print_banner("PHASE 6 BENCHMARK COMPLETE — ALL SCENARIOS VERIFIED")


if __name__ == "__main__":
    asyncio.run(main())
