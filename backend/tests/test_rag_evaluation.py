import json
from pathlib import Path
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.service import DocumentIngestionService, RAGService


@pytest.mark.asyncio
async def test_rag_evaluation_dataset(db_session: AsyncSession):
    dataset_path = Path(__file__).resolve().parent.parent.parent / "evaluation" / "datasets" / "rag_eval_dataset.json"
    knowledge_dir = Path(__file__).resolve().parent.parent.parent / "data" / "knowledge"

    assert dataset_path.exists(), f"Evaluation dataset missing at {dataset_path}"
    assert knowledge_dir.exists(), f"Knowledge dir missing at {knowledge_dir}"

    with open(dataset_path, "r", encoding="utf-8") as f:
        eval_items = json.load(f)

    # 1. Ingest all seed documents into the session
    ingestion_service = DocumentIngestionService(db_session)
    for doc_file in sorted(knowledge_dir.glob("*.md")):
        title = doc_file.stem.replace("-", " ").title()
        content = doc_file.read_text(encoding="utf-8")
        await ingestion_service.ingest_document(
            title=title,
            content=content,
            source=f"runbooks/{doc_file.name}",
            doc_type="runbook",
            metadata={"file_name": doc_file.name},
        )

    # 2. Run evaluation
    rag_service = RAGService(db_session)
    hits_at_3 = 0

    for item in eval_items:
        question = item["question"]
        expected = [s.lower() for s in item["expected_sources"]]
        res = await rag_service.query(query=question, top_k=5)

        retrieved_sources = [s.source.lower() for s in res.sources]
        found_in_top_3 = any(
            any(exp in s for exp in expected) for s in retrieved_sources[:3]
        )
        if found_in_top_3:
            hits_at_3 += 1

    hit_rate = hits_at_3 / len(eval_items)
    # Require at least 80% recall on the deterministic benchmark
    assert hit_rate >= 0.80, f"RAG Recall@3 too low: {hit_rate * 100:.1f}%"
