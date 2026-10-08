from datetime import datetime, timezone
from fastapi import APIRouter, status
from app.core.config import settings
from app.db.session import check_db_health
from app.services.cache_service import check_redis_health
from app.services.kafka_service import check_kafka_health
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Service Health and Diagnostics",
    description="Returns API status, active environment, and verifies database, Redis, and Kafka connectivity.",
)
async def health_check() -> HealthResponse:
    db_healthy = await check_db_health()
    redis_healthy = await check_redis_health()
    kafka_healthy = await check_kafka_health()

    overall_status = "healthy" if db_healthy else "degraded"

    return HealthResponse(
        status=overall_status,
        app_name=settings.APP_NAME,
        environment=settings.APP_ENV,
        database_connected=db_healthy,
        version="1.0.0",
        timestamp=datetime.now(timezone.utc),
        details={
            "debug_mode": settings.DEBUG,
            "llm_provider": settings.LLM_PROVIDER,
            "embedding_model": settings.EMBEDDING_MODEL,
            "redis_connected": redis_healthy,
            "kafka_connected": kafka_healthy,
        },
    )
