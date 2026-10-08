import asyncio
import os
import sys
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.db.session import async_session_factory
from app.rag.service import DocumentIngestionService
from app.core.logging import setup_logging, get_logger

setup_logging("INFO")
logger = get_logger("seed_knowledge")


async def seed_knowledge_base() -> None:
    knowledge_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "knowledge"
    if not knowledge_dir.exists():
        logger.error(f"Knowledge directory not found at {knowledge_dir}")
        return

    logger.info(f"Scanning knowledge directory: {knowledge_dir}")
    md_files = list(knowledge_dir.glob("*.md")) + list(knowledge_dir.glob("*.txt"))

    if not md_files:
        logger.warning("No markdown/text files found to seed.")
        return

    async with async_session_factory() as session:
        service = DocumentIngestionService(session)
        for filepath in md_files:
            title = filepath.stem.replace("-", " ").title()
            content = filepath.read_text(encoding="utf-8")
            source = f"runbooks/{filepath.name}"
            logger.info(f"Ingesting seed doc: '{title}' from {filepath.name}...")
            
            res = await service.ingest_document(
                title=title,
                content=content,
                source=source,
                doc_type="runbook",
                metadata={"file_name": filepath.name, "category": "operations_guide"},
            )
            logger.info(f"-> Ingested {title}: {res.total_chunks} chunks (Doc ID: {res.document_id})")
        await session.commit()

    logger.info("Knowledge base seeding completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed_knowledge_base())
