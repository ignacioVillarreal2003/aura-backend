"""
Tests for BaseConsumer retry-with-delay and message dedup behaviour.
"""
import json
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.infrastructure.messaging.rabbitmq.consumer.base_consumer import BaseConsumer
from app.infrastructure.messaging.rabbitmq.consumer.consumer_utils import RETRY_COUNT_HEADER
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager_settings import RabbitMQManagerSettings
from pydantic import BaseModel


class _Cmd(BaseModel):
    value: int = 1


def _make_manager(settings: RabbitMQManagerSettings) -> MagicMock:
    manager = MagicMock()
    manager.settings = settings
    manager.publish = AsyncMock()
    return manager


class _FakeConsumer(BaseConsumer[_Cmd]):
    def __init__(self, manager, *, fail: bool, dedup_redis=None):
        super().__init__(manager, dedup_redis=dedup_redis)
        self._fail = fail
        self.processed = 0

    @property
    def _queue_name(self) -> str:
        return self._settings.document_ingestion_queue

    def _get_command_type(self):
        return _Cmd

    async def _process(self, envelope):
        self.processed += 1
        if self._fail:
            raise RuntimeError("boom")


def _make_message(*, retry_count: Optional[int] = None, message_id: str = "mid-1") -> MagicMock:
    envelope = MessageEnvelope.wrap(_Cmd(value=1))
    object.__setattr__(envelope, "message_id", message_id)
    body = envelope.to_bytes()
    headers: dict = {"message_id": message_id}
    if retry_count is not None:
        headers[RETRY_COUNT_HEADER] = retry_count
    message = MagicMock()
    message.body = body
    message.headers = headers
    message.ack = AsyncMock()
    message.nack = AsyncMock()
    return message


class TestRetry:
    async def test_first_failure_is_scheduled_for_retry_not_dlq(self):
        settings = RabbitMQManagerSettings(url="amqp://guest:guest@localhost/", max_delivery_attempts=3)
        manager = _make_manager(settings)
        consumer = _FakeConsumer(manager, fail=True)

        message = _make_message(retry_count=None)
        await consumer._handle_message(message)

        manager.publish.assert_awaited_once()
        kwargs = manager.publish.await_args.kwargs
        assert kwargs["exchange_name"] == settings.retry_exchange
        assert kwargs["routing_key"] == settings.document_ingestion_queue
        assert kwargs["headers"][RETRY_COUNT_HEADER] == 1
        message.ack.assert_awaited_once()
        message.nack.assert_not_called()

    async def test_last_attempt_goes_to_dlq(self):
        settings = RabbitMQManagerSettings(url="amqp://guest:guest@localhost/", max_delivery_attempts=3)
        manager = _make_manager(settings)
        consumer = _FakeConsumer(manager, fail=True)

        # retry_count already at max-1 -> next attempt exhausts, goes to DLQ.
        message = _make_message(retry_count=2)
        await consumer._handle_message(message)

        manager.publish.assert_not_called()
        message.nack.assert_awaited_once()
        assert message.nack.await_args.kwargs.get("requeue") is False

    async def test_success_acks_without_retry(self):
        settings = RabbitMQManagerSettings(url="amqp://guest:guest@localhost/", max_delivery_attempts=3)
        manager = _make_manager(settings)
        consumer = _FakeConsumer(manager, fail=False)

        message = _make_message()
        await consumer._handle_message(message)

        message.ack.assert_awaited_once()
        manager.publish.assert_not_called()
        assert consumer.processed == 1


class TestDedup:
    async def test_already_consumed_is_skipped(self):
        settings = RabbitMQManagerSettings(url="amqp://guest:guest@localhost/")
        manager = _make_manager(settings)
        redis = MagicMock()
        redis.exists = AsyncMock(return_value=1)
        redis.set = AsyncMock()
        consumer = _FakeConsumer(manager, fail=False, dedup_redis=redis)

        message = _make_message(message_id="dup-1")
        await consumer._handle_message(message)

        assert consumer.processed == 0
        message.ack.assert_awaited_once()

    async def test_marks_consumed_after_success(self):
        settings = RabbitMQManagerSettings(url="amqp://guest:guest@localhost/")
        manager = _make_manager(settings)
        redis = MagicMock()
        redis.exists = AsyncMock(return_value=0)
        redis.set = AsyncMock()
        consumer = _FakeConsumer(manager, fail=False, dedup_redis=redis)

        message = _make_message(message_id="new-1")
        await consumer._handle_message(message)

        assert consumer.processed == 1
        redis.set.assert_awaited_once()
        message.ack.assert_awaited_once()

    async def test_failure_does_not_mark_consumed(self):
        settings = RabbitMQManagerSettings(url="amqp://guest:guest@localhost/", max_delivery_attempts=3)
        manager = _make_manager(settings)
        redis = MagicMock()
        redis.exists = AsyncMock(return_value=0)
        redis.set = AsyncMock()
        consumer = _FakeConsumer(manager, fail=True, dedup_redis=redis)

        message = _make_message()
        await consumer._handle_message(message)

        redis.set.assert_not_called()
