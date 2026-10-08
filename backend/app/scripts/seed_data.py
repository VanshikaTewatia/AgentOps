import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlalchemy import select
from app.db.session import async_session_factory
from app.models.service import Service
from app.models.incident import Incident
from app.rag.service import DocumentIngestionService
from app.core.logging import setup_logging, get_logger

setup_logging("INFO")
logger = get_logger("seed_data")

INITIAL_SERVICES = [
    {
        "name": "payment-service",
        "description": "Core payments, billing, and checkout transaction gateway",
        "status": "DEGRADED",
        "owner_team": "Payments Engineering",
        "repository_url": "https://github.com/agentops/payment-service",
    },
    {
        "name": "kafka",
        "description": "High-throughput distributed event streaming platform",
        "status": "HEALTHY",
        "owner_team": "Core Infrastructure",
        "repository_url": "https://github.com/agentops/kafka-cluster",
    },
    {
        "name": "redis",
        "description": "Distributed in-memory caching and session state cluster",
        "status": "HEALTHY",
        "owner_team": "Core Infrastructure",
        "repository_url": "https://github.com/agentops/redis-cluster",
    },
    {
        "name": "auth-service",
        "description": "OAuth2 / JWT identity verification and session authority",
        "status": "HEALTHY",
        "owner_team": "Security & Identity",
        "repository_url": "https://github.com/agentops/auth-service",
    },
]


async def seed_all_data() -> None:
    logger.info("--- Starting Deterministic AgentOps Seeding ---")

    async with async_session_factory() as session:
        # 1. Seed Services
        service_map = {}
        for s_data in INITIAL_SERVICES:
            stmt = select(Service).where(Service.name == s_data["name"])
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                svc = Service(
                    id=uuid.uuid4(),
                    name=s_data["name"],
                    description=s_data["description"],
                    status=s_data["status"],
                    owner_team=s_data["owner_team"],
                    repository_url=s_data["repository_url"],
                    metadata_info={"environment": "production", "tier": "tier-1"},
                )
                session.add(svc)
                await session.flush()
                service_map[s_data["name"]] = svc
                logger.info(f"Created service: {svc.name}")
            else:
                service_map[s_data["name"]] = existing
                logger.info(f"Service '{existing.name}' already exists.")

        # 2. Seed Initial Incidents
        pay_svc = service_map.get("payment-service")
        if pay_svc:
            stmt = select(Incident).where(Incident.service_id == pay_svc.id)
            existing_inc = (await session.execute(stmt)).scalars().first()
            if not existing_inc:
                inc = Incident(
                    id=uuid.uuid4(),
                    service_id=pay_svc.id,
                    title="Elevated database connection pool timeouts on payment cluster",
                    description="Active connection pool exhausted (100/100). Checkout API returning HTTP 504 gateway timeout.",
                    severity="HIGH",
                    status="OPEN",
                    root_cause="Connection leak from unindexed long-running queries during flash traffic surge.",
                    resolution_notes="Restart hung worker connections and bump max pool limit.",
                    comments=[
                        {
                            "author": "SRE-OnCall",
                            "comment": "Alert paged on-call engineer at 14:02 UTC.",
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        }
                    ],
                )
                session.add(inc)
                await session.flush()
                logger.info("Created seed incident for payment-service.")

        # 3. Seed Knowledge Base Runbooks
        knowledge_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "knowledge"
        if knowledge_dir.exists():
            md_files = list(knowledge_dir.glob("*.md")) + list(knowledge_dir.glob("*.txt"))
            doc_service = DocumentIngestionService(session)
            for filepath in md_files:
                title = filepath.stem.replace("-", " ").title()
                content = filepath.read_text(encoding="utf-8")
                source = f"runbooks/{filepath.name}"
                res = await doc_service.ingest_document(
                    title=title,
                    content=content,
                    source=source,
                    doc_type="runbook",
                    metadata={"file_name": filepath.name, "category": "operations_guide"},
                )
                logger.info(f"Ingested runbook '{title}': {res.total_chunks} chunks.")

        await session.commit()
        logger.info("Deterministic seeding finished successfully!")


if __name__ == "__main__":
    asyncio.run(seed_all_data())
