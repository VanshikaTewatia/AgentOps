import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../backend")))

from app.db.session import async_session_factory
from app.rag.service import DocumentIngestionService, RAGService
from app.core.logging import setup_logging, get_logger

setup_logging("INFO")
logger = get_logger("rag_evaluator")


async def run_evaluation() -> Dict[str, Any]:
    dataset_path = Path(__file__).resolve().parent.parent / "datasets" / "rag_eval_dataset.json"
    knowledge_dir = Path(__file__).resolve().parent.parent.parent / "data" / "knowledge"

    if not dataset_path.exists():
        raise FileNotFoundError(f"Evaluation dataset not found at {dataset_path}")

    with open(dataset_path, "r", encoding="utf-8") as f:
        eval_items: List[Dict[str, Any]] = json.load(f)

    logger.info(f"Loaded {len(eval_items)} evaluation questions.")

    async with async_session_factory() as session:
        # 1. Ingest Knowledge Base
        ingestion_service = DocumentIngestionService(session)
        for doc_file in sorted(knowledge_dir.glob("*.md")):
            title = doc_file.stem.replace("-", " ").title()
            content = doc_file.read_text(encoding="utf-8")
            source = f"runbooks/{doc_file.name}"
            await ingestion_service.ingest_document(
                title=title,
                content=content,
                source=source,
                doc_type="runbook",
                metadata={"file_name": doc_file.name},
            )

        # 2. Run queries and compute metrics
        rag_service = RAGService(session)
        
        hit_at_1_count = 0
        hit_at_3_count = 0
        reciprocal_ranks: List[float] = []
        latencies_ms: List[float] = []
        results_breakdown: List[Dict[str, Any]] = []

        print("\n" + "=" * 80)
        print(f"{'EVALUATION REPORT: RAG RETRIEVAL & GROUNDING':^80}")
        print("=" * 80)

        for item in eval_items:
            q_id = item["id"]
            question = item["question"]
            expected = [s.lower() for s in item["expected_sources"]]

            start_t = time.perf_counter()
            response = await rag_service.query(query=question, top_k=5)
            duration_ms = (time.perf_counter() - start_t) * 1000
            latencies_ms.append(duration_ms)

            # Check retrieved sources
            retrieved_sources = [s.source.lower() for s in response.sources]
            
            # Calculate rank of first relevant retrieved document
            first_relevant_rank = None
            for rank, s in enumerate(retrieved_sources, start=1):
                if any(exp in s for exp in expected):
                    first_relevant_rank = rank
                    break

            if first_relevant_rank is not None:
                reciprocal_rank = 1.0 / first_relevant_rank
                if first_relevant_rank == 1:
                    hit_at_1_count += 1
                if first_relevant_rank <= 3:
                    hit_at_3_count += 1
            else:
                reciprocal_rank = 0.0

            reciprocal_ranks.append(reciprocal_rank)

            status_str = "HIT (Rank {})".format(first_relevant_rank) if first_relevant_rank else "MISS"
            print(f"[{q_id}] {question[:55]}... -> {status_str} in {duration_ms:.1f}ms")

            results_breakdown.append(
                {
                    "id": q_id,
                    "question": question,
                    "expected_sources": item["expected_sources"],
                    "retrieved_top_sources": [s.source for s in response.sources[:3]],
                    "first_relevant_rank": first_relevant_rank,
                    "latency_ms": round(duration_ms, 2),
                }
            )

        total = len(eval_items)
        hit_rate_1 = (hit_at_1_count / total) * 100
        hit_rate_3 = (hit_at_3_count / total) * 100
        mrr = (sum(reciprocal_ranks) / total)
        avg_latency = sum(latencies_ms) / total

        print("-" * 80)
        print(f"Total Evaluated Questions : {total}")
        print(f"Hit Rate @ 1 (Top-1 Recall): {hit_rate_1:.1f}% ({hit_at_1_count}/{total})")
        print(f"Hit Rate @ 3 (Top-3 Recall): {hit_rate_3:.1f}% ({hit_at_3_count}/{total})")
        print(f"Mean Reciprocal Rank (MRR): {mrr:.4f}")
        print(f"Average Retrieval Latency : {avg_latency:.2f} ms")
        print("=" * 80 + "\n")

        return {
            "total_questions": total,
            "hit_rate_at_1_percent": round(hit_rate_1, 2),
            "hit_rate_at_3_percent": round(hit_rate_3, 2),
            "mrr": round(mrr, 4),
            "avg_latency_ms": round(avg_latency, 2),
            "breakdown": results_breakdown,
        }


if __name__ == "__main__":
    asyncio.run(run_evaluation())
