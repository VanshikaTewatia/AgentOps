"""
Phase 7 Agent Evaluation, Observability & Reliability Benchmark Demo.
Executes live against local PostgreSQL database to:
1. Run all 20 benchmark cases from agentops-eval-v1
2. Measure Routing Accuracy, Tool Selection Accuracy, Grounding, Provenance, Conflict Handling, Approval Safety
3. Measure Latency (Avg & P95) and token metrics
4. Persist evaluation run & case results in PostgreSQL
5. Output structured machine-readable JSON & human-readable evaluation summary
6. Display a full live execution trace demonstrating complete observability
"""

import asyncio
import json
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.db.session import async_session_factory
from app.services.evaluation_service import EvaluationRunner
from app.rag.service import DocumentIngestionService
from app.agents.graph import run_agent_workflow


def print_banner(title: str):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


async def main():
    print_banner("AGENTOPS PHASE 7 — AGENT EVALUATION & OBSERVABILITY BENCHMARK")

    async with async_session_factory() as session:
        # Seed operational knowledge base
        knowledge_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "knowledge"
        if knowledge_dir.exists():
            ingestion = DocumentIngestionService(session)
            for doc_path in sorted(knowledge_dir.glob("*.md")):
                title = doc_path.stem.replace("-", " ").title()
                content = doc_path.read_text(encoding="utf-8")
                await ingestion.ingest_document(
                    title=title,
                    content=content,
                    source=f"runbooks/{doc_path.name}",
                    doc_type="runbook",
                    metadata={"file_name": doc_path.name},
                )
            await session.commit()

        # -------------------------------------------------------------
        # 1. RUN 20-CASE REPEATABLE BENCHMARK
        # -------------------------------------------------------------
        print("\n--> Executing 20-Case Benchmark on dataset: 'agentops-eval-v1'...")
        runner = EvaluationRunner(session)
        eval_run = await runner.run_evaluation(dataset_name="agentops-eval-v1")

        # -------------------------------------------------------------
        # 2. HUMAN-READABLE EVALUATION REPORT
        # -------------------------------------------------------------
        print_banner("EVALUATION RUN SUMMARY")
        print(f"Run ID                   : {eval_run.id}")
        print(f"Dataset                  : {eval_run.dataset_name}")
        print(f"Model Provider           : {eval_run.model_provider}")
        print(f"Total Benchmark Cases    : {eval_run.total_cases}")
        print(f"Passed Cases             : {eval_run.passed_cases} / {eval_run.total_cases} ({eval_run.passed_cases/eval_run.total_cases*100:.1f}%)")
        print(f"Failed Cases             : {eval_run.failed_cases}")
        print("-" * 80)
        print(f"Routing Accuracy         : {eval_run.routing_accuracy * 100:.2f}%")
        print(f"Tool Selection Accuracy  : {eval_run.tool_selection_accuracy * 100:.2f}%")
        print(f"Evidence Grounding Rate  : {eval_run.grounding_rate * 100:.2f}%")
        print(f"Provenance Rate          : {eval_run.provenance_rate * 100:.2f}%")
        print(f"Conflict Detection Rate  : {eval_run.conflict_detection_rate * 100:.2f}%")
        print(f"Approval Safety Rate     : {eval_run.approval_safety_rate * 100:.2f}%")
        print("-" * 80)
        print(f"Average Latency          : {eval_run.avg_latency_ms:.2f} ms")
        print(f"P95 Latency              : {eval_run.p95_latency_ms:.2f} ms")
        print(f"Total Tokens Tracked     : {eval_run.total_tokens}")

        # -------------------------------------------------------------
        # 3. PER-CATEGORY BREAKDOWN
        # -------------------------------------------------------------
        print_banner("PER-CATEGORY EVALUATION BREAKDOWN")
        categories = {}
        for r in eval_run.results:
            cat = r.category
            if cat not in categories:
                categories[cat] = {"total": 0, "passed": 0, "latencies": []}
            categories[cat]["total"] += 1
            if r.status == "PASSED":
                categories[cat]["passed"] += 1
            categories[cat]["latencies"].append(r.latency_ms)

        print(f"{'Category':<35} | {'Cases':<6} | {'Pass Rate':<10} | {'Avg Latency (ms)':<15}")
        print("-" * 75)
        for cat, stats in categories.items():
            pass_pct = (stats["passed"] / stats["total"]) * 100
            avg_l = sum(stats["latencies"]) / len(stats["latencies"])
            print(f"{cat:<35} | {stats['total']:<6} | {pass_pct:>8.1f}% | {avg_l:>15.2f}")

        # -------------------------------------------------------------
        # 4. MACHINE-READABLE JSON REPORT
        # -------------------------------------------------------------
        report_data = {
            "evaluation_id": str(eval_run.id),
            "dataset": eval_run.dataset_name,
            "total_cases": eval_run.total_cases,
            "passed": eval_run.passed_cases,
            "failed": eval_run.failed_cases,
            "routing_accuracy": eval_run.routing_accuracy,
            "tool_selection_accuracy": eval_run.tool_selection_accuracy,
            "grounding_rate": eval_run.grounding_rate,
            "provenance_rate": eval_run.provenance_rate,
            "conflict_detection_rate": eval_run.conflict_detection_rate,
            "approval_safety_rate": eval_run.approval_safety_rate,
            "avg_latency_ms": eval_run.avg_latency_ms,
            "p95_latency_ms": eval_run.p95_latency_ms,
            "total_tokens": eval_run.total_tokens,
            "created_at": eval_run.created_at.isoformat(),
        }
        report_path = Path(__file__).resolve().parent.parent.parent.parent / "evaluation" / "reports" / "phase7_eval_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
        print(f"\n[Artifact] Machine-readable report saved to: {report_path.name}")

        # -------------------------------------------------------------
        # 5. OBSERVABILITY DEMONSTRATION (COMPLETE EXECUTION TRACE)
        # -------------------------------------------------------------
        print_banner("OBSERVABILITY DEMONSTRATION: FULL EXECUTION TRACE")
        trace_query = "Why is payment-service experiencing database connection pool exhaustion?"
        print(f"Target Query: '{trace_query}'\n")

        trace_res = await run_agent_workflow(
            user_request=trace_query,
            conversation_id="obs-trace-demo",
            session=session,
        )

        print(f"Trace Run ID        : {trace_res.id}")
        print(f"Total Execution Time: {trace_res.total_latency_ms} ms")
        print(f"Total Tokens        : {trace_res.total_tokens}")
        print(f"Specialists Active  : {trace_res.agents_used}")
        print(f"Tools Invoked       : {trace_res.tools_used}")
        print(f"Evidence Collected  : {trace_res.evidence_count}")
        print(f"Approval Required   : {trace_res.approval_required}")
        print(f"Status              : {trace_res.status}")

        print("\n[Chronological Node & Event Trace]:")
        for ev in trace_res.events:
            dur = f"{ev.duration_ms:.1f}ms" if ev.duration_ms is not None else "0.0ms"
            print(f"  [{ev.node_name:<16}] {ev.event_type:<20} duration={dur:<8} payload={str(ev.payload)[:60]}")

        print("\n[Tool Execution Telemetry]:")
        for te in trace_res.tool_executions:
            lat = f"{te.latency_ms:.1f}ms" if te.latency_ms else "0.0ms"
            print(f"  * {te.tool_name:<22} status={te.status:<8} latency={lat:<8} input={str(te.tool_input)}")

    print_banner("PHASE 7 VERIFICATION COMPLETE — ALL METRICS RECORDED")


if __name__ == "__main__":
    asyncio.run(main())
