import json
import logging
import asyncio
from typing import Optional
from aio_pika import IncomingMessage, RobustChannel

from app.application.exceptions.app_exceptions import RabbitMQError
from app.application.services.document_question_service.document_question_service import QuestionService
from app.configuration.environment_variables import environment_variables
from app.domain.dtos.document_question_request import QuestionRequest
from app.infrastructure.messaging.rabbitmq_client import RabbitmqClient

logger = logging.getLogger(__name__)


class QuestionListener:
    def __init__(self,
                 rabbitmq_client: RabbitmqClient,
                 question_service: QuestionService) -> None:
        self.rabbitmq_client: RabbitmqClient = rabbitmq_client
        self.question_service: QuestionService = question_service
        self.question_queue: str = environment_variables.question_queue
        self.answer_queue: str = environment_variables.answer_queue
        self.consumer_task: Optional[asyncio.Task] = None

    async def start_consuming(self,
                              prefetch_count: int = 1) -> None:
        try:
            await self.rabbitmq_client.connect()
            channel: RobustChannel = await self.rabbitmq_client.get_channel()
            queue = await channel.declare_queue(self.question_queue, durable=True)

            await queue.bind(self.rabbitmq_client.exchange, routing_key=self.question_queue)
            await channel.set_qos(prefetch_count=prefetch_count)
            await queue.consume(self._on_message, no_ack=False)

            logger.info("Consumer started")

            self.consumer_task = asyncio.current_task()

        except Exception as e:
            logger.exception("Failed to start consumer")
            raise RabbitMQError("Failed to start consumer") from e

    async def _on_message(self,
                          message: IncomingMessage) -> None:
        try:
            payload = json.loads(message.body.decode())
            request = QuestionRequest(**payload)

            logger.info("Processing message")

            result = await self.question_service.generate_response(request)

            response_payload = {"answer": result.answer}
            await self.rabbitmq_client.publish(
                response_payload,
                routing_key=self.answer_queue,
            )

            logger.info("LLM response generated")
            await message.ack()

        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
            await message.nack(requeue=False)

        except Exception as e:
            logger.exception("Error processing message")
            await message.nack(requeue=False)
            raise RabbitMQError("Error processing message") from e

    def stop_consuming(self) -> None:
        if self.consumer_task:
            self.consumer_task.cancel()
            logger.info("Consumer task cancelled")
