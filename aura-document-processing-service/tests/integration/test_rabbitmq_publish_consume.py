"""RabbitMQ publish and consume one message (Docker `queue` service)."""

import asyncio
import os

import aio_pika
import pytest

from tests.integration.conftest import integration_rabbitmq_url

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_publish_then_consume_roundtrip() -> None:
    url = integration_rabbitmq_url()
    queue_name = f"pytest.integration.{os.getpid()}"
    body = b"hello-rabbit"

    connection = await aio_pika.connect_robust(url)
    try:
        channel = await connection.channel()
        queue = await channel.declare_queue(queue_name, auto_delete=True)
        await channel.default_exchange.publish(
            aio_pika.Message(body),
            routing_key=queue.name,
        )
        msg = await asyncio.wait_for(queue.get(), timeout=10.0)
        assert msg is not None
        assert msg.body == body
        await msg.ack()
    finally:
        await connection.close()
