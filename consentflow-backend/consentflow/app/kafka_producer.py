"""
kafka_producer.py — Async Kafka producer for consent-revocation events.

Lifecycle
---------
The producer is initialised once at application startup (via FastAPI lifespan)
and stored on ``app.state.kafka_producer``.  It is gracefully stopped on
shutdown.  Every other module obtains the singleton via the FastAPI ``Request``
object (``request.app.state.kafka_producer``).

Published topic
---------------
``consent.revoked``  (configured via KAFKA_TOPIC_REVOKE env var)

Message schema
--------------
{
    "event":     "consent.revoked",
    "user_id":   "<uuid-string>",
    "purpose":   "<purpose-string>",
    "timestamp": "<ISO-8601 UTC string>"
}
"""
from __future__ import annotations

import json
import logging
from typing import Any

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

from consentflow.app.config import settings

logger = logging.getLogger(__name__)

# ── Lifecycle ──────────────────────────────────────────────────────────────────


async def create_kafka_producer() -> AIOKafkaProducer:
    """
    Instantiate and start an AIOKafkaProducer.

    The producer serialises values as UTF-8 encoded JSON.
    Keys are UTF-8 encoded strings (user_id).
    """
    producer: AIOKafkaProducer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_broker_url,
        # Serialise values as JSON bytes  ─────────────────────────────────────
        value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
        # Serialise keys as UTF-8 bytes ───────────────────────────────────────
        key_serializer=lambda k: k.encode("utf-8") if k else None,
        # Durability: wait for leader ack (good default for audit events) ─────
        acks="all",
        # Retry up to 3 times on transient errors ─────────────────────────────
        retry_backoff_ms=200,
        request_timeout_ms=10_000,
    )
    await producer.start()
    logger.info(
        "Kafka producer started — broker=%s  topic=%s",
        settings.kafka_broker_url,
        settings.kafka_topic_revoke,
    )
    return producer


async def close_kafka_producer(producer: AIOKafkaProducer) -> None:
    """Flush pending messages and stop the producer."""
    await producer.stop()
    logger.info("Kafka producer stopped")


# ── Publish helper ─────────────────────────────────────────────────────────────


async def publish_revocation(
    producer: AIOKafkaProducer,
    user_id: str,
    purpose: str,
    timestamp: str,
) -> None:
    """
    Publish a ``consent.revoked`` event to Kafka.

    Parameters
    ----------
    producer:  The running AIOKafkaProducer from app.state.
    user_id:   UUID of the user whose consent was revoked (as a string).
    purpose:   The revoked processing purpose.
    timestamp: ISO-8601 UTC timestamp of the revocation event.

    Raises
    ------
    KafkaError  If the broker rejects or cannot reach the message.  The caller
                is expected to catch this and apply its own fallback strategy.
    """
    message: dict[str, Any] = {
        "event": "consent.revoked",
        "user_id": user_id,
        "purpose": purpose,
        "timestamp": timestamp,
    }

    try:
        record_metadata = await producer.send_and_wait(
            topic=settings.kafka_topic_revoke,
            value=message,
            # Use user_id as the partition key so all events for the same
            # user land on the same partition (preserved ordering guarantee).
            key=user_id,
        )
        logger.info(
            "Kafka event published — topic=%s partition=%d offset=%d user_id=%s purpose=%s",
            record_metadata.topic,
            record_metadata.partition,
            record_metadata.offset,
            user_id,
            purpose,
        )
    except KafkaError as exc:
        logger.error(
            "Kafka publish failed — user_id=%s purpose=%s error=%s",
            user_id,
            purpose,
            exc,
        )
        # Re-raise so callers can decide how to handle (207, DLQ, etc.)
        raise
