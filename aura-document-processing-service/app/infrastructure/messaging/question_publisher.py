import logging

from app.application.exceptions.api_exceptions import MessagingError
from app.configuration.environment_variables import environment_variables
from app.domain.dtos.question_response import QuestionResponse
from app.infrastructure.messaging.interfaces.question_publisher_interface import QuestionPublisherInterface
from app.infrastructure.messaging.rabbitmq_client import RabbitmqClient

logger = logging.getLogger(__name__)


class QuestionPublisher(QuestionPublisherInterface):
    def __init__(self,
                 rabbitmq_client: RabbitmqClient):
        self.rabbitmq_client = rabbitmq_client
        self.queue = environment_variables.question_queue
        self.exchange = environment_variables.exchange

    def publish_question(self,
                         question: QuestionResponse) -> None:
        try:
            message = {
                "question": question.question,
                "context": question.context,
                "messages": question.messages,
            }

            self.rabbitmq_client.publish(
                message,
                routing_key=self.queue,
                exchange=self.exchange)

            logger.info(
                "Published document event"
            )
        except Exception as e:
            logger.exception("Failed to publish document event")
            raise MessagingError("Failed to publish document message") from e
