import json
from typing import Any, Dict, Optional
from aiokafka import AIOKafkaProducer
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_kafka_producer: Optional[AIOKafkaProducer] = None


async def get_kafka_producer() -> Optional[AIOKafkaProducer]:
    """Provides a singleton async Kafka producer."""
    global _kafka_producer
    if _kafka_producer is None:
        try:
            producer = AIOKafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                request_timeout_ms=2000,
            )
            await producer.start()
            _kafka_producer = producer
        except Exception as e:
            logger.warning(f"Failed to start Kafka producer on {settings.KAFKA_BOOTSTRAP_SERVERS}: {e}")
            return None
    return _kafka_producer


async def check_kafka_health() -> bool:
    """Checks Kafka broker availability."""
    try:
        producer = await get_kafka_producer()
        if producer:
            # Check cluster metadata
            client = producer.client
            return client.ready()
        return False
    except Exception as e:
        logger.debug(f"Kafka health check failed: {e}")
        return False


class KafkaEventPublisher:
    """Publishes agent lifecycle events to Kafka with graceful local degradation."""

    @staticmethod
    async def publish_event(
        event_type: str,
        payload: Dict[str, Any],
        topic: Optional[str] = None,
    ) -> bool:
        target_topic = topic or settings.KAFKA_AGENT_EVENTS_TOPIC
        try:
            producer = await get_kafka_producer()
            if producer:
                await producer.send_and_wait(
                    target_topic,
                    {
                        "event_type": event_type,
                        "payload": payload,
                    },
                )
                return True
        except Exception as e:
            logger.debug(f"Failed to publish Kafka event to {target_topic}: {e}")
        return False
