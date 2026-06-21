import json
import logging
import time
from typing import Any, Optional
import redis.asyncio as aioredis

from app.infrastructure.messaging.rabbitmq.interfaces.rabbitmq_manager_interface import RabbitMQManagerInterface
from app.infrastructure.persistence.memory_database.redis_client.redis_client_settings import RedisClientSettings

logger = logging.getLogger(__name__)


class RedisOutboxLite:
    def __init__(
            self,
            *,
            redis_client: aioredis.Redis,
            rabbitmq_manager: RabbitMQManagerInterface,
            settings: Optional[RedisClientSettings] = None,
    ) -> None:
        self._redis = redis_client
        self._rabbitmq_manager = rabbitmq_manager
        self._settings = settings or RedisClientSettings()
        self._key_prefix = f"{self._settings.key_prefix}:outbox_lite"
        self._pending_set_key = f"{self._key_prefix}:pending"

    def _event_key(self, event_id: str) -> str:
        return f"{self._key_prefix}:event:{event_id}"

    def _published_marker_key(self, event_type: str, aggregate_id: str) -> str:
        return f"{self._key_prefix}:published:{event_type}:{aggregate_id}"

    async def publish_or_enqueue(
            self,
            *,
            event_id: str,
            event_type: str,
            aggregate_id: str,
            routing_key: str,
            body: bytes,
            headers: Optional[dict[str, Any]] = None,
            exchange_name: Optional[str] = None,
            persistent: bool = True,
    ) -> str:
        try:
            await self._rabbitmq_manager.publish(
                routing_key=routing_key,
                body=body,
                headers=headers,
                exchange_name=exchange_name,
                persistent=persistent,
            )
            await self.mark_published(event_type=event_type, aggregate_id=aggregate_id)
            return event_id
        except Exception as e:
            logger.warning(
                "Publish failed; enqueueing event in redis outbox-lite.",
                extra={
                    "event_id": event_id,
                    "event_type": event_type,
                    "aggregate_id": aggregate_id,
                    "routing_key": routing_key,
                    "exception_type": type(e).__name__,
                },
            )
            await self.enqueue_pending(
                event_id=event_id,
                event_type=event_type,
                aggregate_id=aggregate_id,
                routing_key=routing_key,
                body=body,
                headers=headers or {},
                exchange_name=exchange_name,
                persistent=persistent,
                attempts=0,
                next_retry_at=int(time.time()),
                last_error=type(e).__name__,
            )
            return event_id

    async def enqueue_pending(
            self,
            *,
            event_id: str,
            event_type: str,
            aggregate_id: str,
            routing_key: str,
            body: bytes,
            headers: dict[str, Any],
            exchange_name: Optional[str],
            persistent: bool,
            attempts: int,
            next_retry_at: int,
            last_error: Optional[str],
    ) -> None:
        payload = {
            "event_id": event_id,
            "event_type": event_type,
            "aggregate_id": aggregate_id,
            "routing_key": routing_key,
            "body": body.decode("utf-8"),
            "headers": headers,
            "exchange_name": exchange_name,
            "persistent": persistent,
            "attempts": attempts,
            "next_retry_at": next_retry_at,
            "last_error": last_error,
            "updated_at": int(time.time()),
        }
        event_key = self._event_key(event_id)
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.set(event_key, json.dumps(payload), ex=self._settings.outbox_pending_ttl_seconds)
            pipe.sadd(self._pending_set_key, event_id)
            await pipe.execute()

    async def mark_published(
            self,
            *,
            event_type: str,
            aggregate_id: str,
    ) -> None:
        marker_key = self._published_marker_key(event_type, aggregate_id)
        await self._redis.set(marker_key, "1", ex=self._settings.outbox_published_marker_ttl_seconds)

    async def has_been_published(
            self,
            *,
            event_type: str,
            aggregate_id: str,
    ) -> bool:
        marker_key = self._published_marker_key(event_type, aggregate_id)
        return bool(await self._redis.exists(marker_key))

    async def drain_pending_batch(
            self,
            *,
            limit: Optional[int] = None,
    ) -> int:
        batch_size = limit or self._settings.outbox_retry_batch_size
        event_ids = await self._redis.srandmember(self._pending_set_key, number=batch_size)
        if not event_ids:
            return 0

        processed = 0
        now_epoch = int(time.time())
        for event_id in event_ids:
            event_key = self._event_key(event_id)
            raw = await self._redis.get(event_key)
            if raw is None:
                await self._redis.srem(self._pending_set_key, event_id)
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                await self._redis.delete(event_key)
                await self._redis.srem(self._pending_set_key, event_id)
                continue

            if int(event.get("next_retry_at", now_epoch)) > now_epoch:
                continue

            processed += 1
            await self._retry_single_event(event_id=event_id, event=event, now_epoch=now_epoch)

        return processed

    async def _retry_single_event(
            self,
            *,
            event_id: str,
            event: dict[str, Any],
            now_epoch: int,
    ) -> None:
        attempts = int(event.get("attempts", 0))
        try:
            await self._rabbitmq_manager.publish(
                routing_key=event["routing_key"],
                body=event["body"].encode("utf-8"),
                headers=event.get("headers") or {},
                exchange_name=event.get("exchange_name"),
                persistent=bool(event.get("persistent", True)),
            )
            await self.mark_published(
                event_type=str(event["event_type"]),
                aggregate_id=str(event["aggregate_id"]),
            )
            await self._redis.delete(self._event_key(event_id))
            await self._redis.srem(self._pending_set_key, event_id)
            logger.info(
                "Pending outbox-lite event published successfully.",
                extra={
                    "event_id": event_id,
                    "event_type": event.get("event_type"),
                    "aggregate_id": event.get("aggregate_id"),
                    "attempts": attempts + 1,
                },
            )
        except Exception as e:
            new_attempts = attempts + 1
            if new_attempts >= self._settings.outbox_max_retry_attempts:
                await self._redis.delete(self._event_key(event_id))
                await self._redis.srem(self._pending_set_key, event_id)
                logger.error(
                    "Pending outbox-lite event was discarded after max retries.",
                    extra={
                        "event_id": event_id,
                        "event_type": event.get("event_type"),
                        "aggregate_id": event.get("aggregate_id"),
                        "attempts": new_attempts,
                        "error": type(e).__name__,
                    },
                )
                return

            delay = min(
                self._settings.outbox_retry_backoff_max_seconds,
                self._settings.outbox_retry_backoff_min_seconds * (2 ** max(0, new_attempts - 1)),
            )
            event["attempts"] = new_attempts
            event["next_retry_at"] = now_epoch + int(delay)
            event["last_error"] = type(e).__name__
            await self._redis.set(
                self._event_key(event_id),
                json.dumps(event),
                ex=self._settings.outbox_pending_ttl_seconds,
            )
            logger.warning(
                "Pending outbox-lite event publish failed; retry scheduled.",
                extra={
                    "event_id": event_id,
                    "event_type": event.get("event_type"),
                    "aggregate_id": event.get("aggregate_id"),
                    "attempts": new_attempts,
                    "next_retry_in_seconds": int(delay),
                    "error": type(e).__name__,
                },
            )
