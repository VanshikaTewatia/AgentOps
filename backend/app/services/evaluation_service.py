import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import get_logger
from app.agents.graph import run_agent_workflow
from app.models.evaluation import EvaluationRun, EvaluationCaseResult
from app.schemas.evaluation import (
    EvaluationCaseSchema,
    EvaluationCaseResultSchema,
    EvaluationRunResponse,
)

logger = get_logger(__name__)


class EvaluationRunner:
    """
    Evaluation & Observability Benchmark Runner:
    Executes repeatable operational datasets, evaluates retrieval, routing,
    tool selection, evidence grounding, provenance, and approval safety,
    and persists execution runs in PostgreSQL.
    """

    def __init__(self, session: AsyncSession, dataset_path: Optional[Path] = None):
        self.session = session
        self.dataset_path = dataset_path or (
            Path(__file__).resolve().parent.parent.parent.parent / "evaluation" / "datasets" / "agentops_eval_v1.json"
        )

    def load_dataset(self, max_cases: Optional[int] = None) -> List[EvaluationCaseSchema]:
        """Loads and parses the evaluation benchmark dataset."""
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Evaluation dataset not found at {self.dataset_path}")

        with open(self.dataset_path, "r", encoding="utf-8") as f:
            raw_cases = json.load(f)

        cases = [EvaluationCaseSchema.model_validate(c) for c in raw_cases]
        if max_cases:
            cases = cases[:max_cases]
        return cases

    async def run_evaluation(
        self,
        dataset_name: str = "agentops-eval-v1",
        max_cases: Optional[int] = None,
    ) -> EvaluationRunResponse:
        """Runs the complete evaluation benchmark suite across all cases."""
        cases = self.load_dataset(max_cases=max_cases)
        logger.info(f"Starting Evaluation Run on {len(cases)} cases from '{dataset_name}'")

        run_uuid = uuid.uuid4()
        case_results: List[EvaluationCaseResult] = []
        latencies: List[float] = []
        total_tokens = 0

        routing_correct_count = 0
        tool_correct_count = 0
        grounded_count = 0
        provenance_count = 0
        conflict_handled_count = 0
        approval_safety_count = 0
        passed_cases = 0

        eval_run_rec = EvaluationRun(
            id=run_uuid,
            dataset_name=dataset_name,
            model_provider=settings.LLM_PROVIDER,
            total_cases=len(cases),
        )
        self.session.add(eval_run_rec)
        await self.session.commit()

        for case in cases:
            case_start_t = time.perf_counter()
            try:
                # Execute agent workflow
                resp = await run_agent_workflow(
                    user_request=case.user_query,
                    conversation_id=f"eval-{case.case_id}-{uuid.uuid4().hex[:6]}",
                    session=self.session,
                )
                duration_ms = (time.perf_counter() - case_start_t) * 1000
                latencies.append(duration_ms)
                tokens = resp.total_tokens or 0
                total_tokens += tokens

                # 1. Routing Evaluation
                actual_agents = resp.agents_used or ["SupervisorAgent"]
                # Required specialist agents present?
                missing_agents = [a for a in case.expected_agents if a not in actual_agents]
                routing_ok = len(missing_agents) == 0
                if routing_ok:
                    routing_correct_count += 1

                # 2. Tool Selection Evaluation
                actual_tools = resp.tools_used or []
                missing_tools = [t for t in case.expected_tools if t not in actual_tools and t != "search_knowledge_base"]
                tool_ok = len(missing_tools) == 0 or len(case.expected_tools) == 0
                if tool_ok:
                    tool_correct_count += 1

                # 3. Grounding & Evidence Evaluation
                grounded_ok = resp.evidence_count > 0 or len(case.expected_evidence_types) == 0
                if grounded_ok:
                    grounded_count += 1

                # 4. Provenance Attribution Evaluation
                provenance_ok = "Provenance" in (resp.final_answer or "") or resp.evidence_count > 0
                if provenance_ok:
                    provenance_count += 1

                # 5. Approval Safety Evaluation
                if case.requires_approval:
                    approval_ok = resp.status == "WAITING_APPROVAL" and resp.approval_required is True
                else:
                    approval_ok = resp.status == case.expected_final_state
                if approval_ok:
                    approval_safety_count += 1

                # 6. Conflict & Answer Quality
                conflict_ok = True
                if case.category == "Conflict handling":
                    conflict_ok = "Conflicting" in (resp.final_answer or "") or "Notice" in (resp.final_answer or "")
                if conflict_ok:
                    conflict_handled_count += 1

                # Overall Case Status
                case_passed = (
                    routing_ok
                    and tool_ok
                    and approval_ok
                    and (resp.status in ("COMPLETED", "WAITING_APPROVAL"))
                )
                if case_passed:
                    passed_cases += 1

                case_result_rec = EvaluationCaseResult(
                    id=uuid.uuid4(),
                    run_id=run_uuid,
                    case_id=case.case_id,
                    category=case.category,
                    query=case.user_query,
                    status="PASSED" if case_passed else "FAILED",
                    actual_agents=actual_agents,
                    expected_agents=case.expected_agents,
                    actual_tools=actual_tools,
                    expected_tools=case.expected_tools,
                    routing_correct=routing_ok,
                    tool_selection_correct=tool_ok,
                    grounded=grounded_ok,
                    provenance_valid=provenance_ok,
                    approval_safety_passed=approval_ok,
                    conflict_handled=conflict_ok,
                    evidence_count=resp.evidence_count,
                    latency_ms=round(duration_ms, 2),
                    tokens_used=tokens,
                    details={
                        "missing_agents": missing_agents,
                        "missing_tools": missing_tools,
                        "status": resp.status,
                    },
                )
                case_results.append(case_result_rec)
                self.session.add(case_result_rec)
                await self.session.commit()

            except Exception as e:
                logger.error(f"Error evaluating case '{case.case_id}': {e}")
                duration_ms = (time.perf_counter() - case_start_t) * 1000
                latencies.append(duration_ms)
                case_result_rec = EvaluationCaseResult(
                    id=uuid.uuid4(),
                    run_id=run_uuid,
                    case_id=case.case_id,
                    category=case.category,
                    query=case.user_query,
                    status="FAILED",
                    actual_agents=[],
                    expected_agents=case.expected_agents,
                    actual_tools=[],
                    expected_tools=case.expected_tools,
                    routing_correct=False,
                    tool_selection_correct=False,
                    grounded=False,
                    provenance_valid=False,
                    approval_safety_passed=False,
                    conflict_handled=False,
                    evidence_count=0,
                    latency_ms=round(duration_ms, 2),
                    tokens_used=0,
                    error=str(e),
                )
                case_results.append(case_result_rec)
                self.session.add(case_result_rec)
                await self.session.commit()

        # Compute Aggregated Run Metrics
        num_cases = len(cases)
        avg_lat = float(np.mean(latencies)) if latencies else 0.0
        p95_lat = float(np.percentile(latencies, 95)) if latencies else 0.0

        eval_run_rec.passed_cases = passed_cases
        eval_run_rec.failed_cases = num_cases - passed_cases
        eval_run_rec.routing_accuracy = round(routing_correct_count / num_cases, 4) if num_cases else 0.0
        eval_run_rec.tool_selection_accuracy = round(tool_correct_count / num_cases, 4) if num_cases else 0.0
        eval_run_rec.grounding_rate = round(grounded_count / num_cases, 4) if num_cases else 0.0
        eval_run_rec.provenance_rate = round(provenance_count / num_cases, 4) if num_cases else 0.0
        eval_run_rec.conflict_detection_rate = round(conflict_handled_count / num_cases, 4) if num_cases else 0.0
        eval_run_rec.approval_safety_rate = round(approval_safety_count / num_cases, 4) if num_cases else 0.0
        eval_run_rec.avg_latency_ms = round(avg_lat, 2)
        eval_run_rec.p95_latency_ms = round(p95_lat, 2)
        eval_run_rec.total_tokens = total_tokens
        eval_run_rec.estimated_cost_usd = 0.0  # Configurable pricing model
        eval_run_rec.metrics = {
            "pass_rate": round(passed_cases / num_cases, 4) if num_cases else 0.0,
            "total_cases": num_cases,
        }

        await self.session.commit()

        # Query back complete record with eager loading
        q = await self.session.execute(
            select(EvaluationRun)
            .options(selectinload(EvaluationRun.results))
            .where(EvaluationRun.id == run_uuid)
        )
        saved = q.scalar_one()

        return EvaluationRunResponse(
            id=saved.id,
            dataset_name=saved.dataset_name,
            model_provider=saved.model_provider,
            total_cases=saved.total_cases,
            passed_cases=saved.passed_cases,
            failed_cases=saved.failed_cases,
            routing_accuracy=saved.routing_accuracy,
            tool_selection_accuracy=saved.tool_selection_accuracy,
            grounding_rate=saved.grounding_rate,
            provenance_rate=saved.provenance_rate,
            conflict_detection_rate=saved.conflict_detection_rate,
            approval_safety_rate=saved.approval_safety_rate,
            avg_latency_ms=saved.avg_latency_ms,
            p95_latency_ms=saved.p95_latency_ms,
            total_tokens=saved.total_tokens,
            estimated_cost_usd=saved.estimated_cost_usd,
            metrics=saved.metrics or {},
            created_at=saved.created_at,
            results=[
                EvaluationCaseResultSchema(
                    case_id=r.case_id,
                    category=r.category,
                    query=r.query,
                    status=r.status,
                    actual_agents=r.actual_agents or [],
                    expected_agents=r.expected_agents or [],
                    actual_tools=r.actual_tools or [],
                    expected_tools=r.expected_tools or [],
                    routing_correct=r.routing_correct,
                    tool_selection_correct=r.tool_selection_correct,
                    grounded=r.grounded,
                    provenance_valid=r.provenance_valid,
                    approval_safety_passed=r.approval_safety_passed,
                    conflict_handled=r.conflict_handled,
                    evidence_count=r.evidence_count,
                    latency_ms=r.latency_ms,
                    tokens_used=r.tokens_used,
                    details=r.details or {},
                    error=r.error,
                )
                for r in saved.results
            ],
        )
