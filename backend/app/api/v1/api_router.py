from fastapi import APIRouter
from app.api.v1.endpoints import health, documents, rag, agent, approvals, evaluations, services, incidents

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health & Diagnostics"])
api_router.include_router(documents.router, prefix="/documents", tags=["Knowledge & Documents"])
api_router.include_router(rag.router, prefix="/rag", tags=["Retrieval-Augmented Generation"])
api_router.include_router(agent.router, prefix="/agent", tags=["Agent Orchestration"])
api_router.include_router(approvals.router, prefix="/approvals", tags=["Human Approval Gates"])
api_router.include_router(evaluations.router, prefix="/evaluations", tags=["Evaluation & Observability"])
api_router.include_router(services.router, prefix="/services", tags=["Services Telemetry"])
api_router.include_router(incidents.router, prefix="/incidents", tags=["Incidents Management"])
