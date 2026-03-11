import json
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis

from app.core.config import settings

redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=False)


async def publish_document_status(
    document_id: uuid.UUID,
    status: str,
    detail: str = "",
) -> None:
    """Publish document status update via Redis pub/sub (async version)."""
    channel = "document-status"
    payload = json.dumps({
        "document_id": str(document_id),
        "status": status,
        "detail": detail,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    await redis_client.publish(channel, payload)


def publish_document_status_sync(
    document_id: uuid.UUID,
    status: str,
    detail: str = "",
) -> None:
    """Publish document status update via Redis pub/sub (sync version for Celery)."""
    import redis as sync_redis

    r = sync_redis.from_url(settings.REDIS_URL, decode_responses=False)
    channel = "document-status"
    payload = json.dumps({
        "document_id": str(document_id),
        "status": status,
        "detail": detail,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    r.publish(channel, payload)
    r.close()
