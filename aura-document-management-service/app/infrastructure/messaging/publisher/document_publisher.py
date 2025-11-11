import logging

from app.application.exceptions.exceptions import MessagingError
from app.configuration.environment_variables import environment_variables
from app.infrastructure.messaging.publisher.interfaces.document_publisher_interface import DocumentPublisherInterface
from app.infrastructure.messaging.rabbitmq_client import RabbitmqClient


logger = logging.getLogger(__name__)


class DocumentPublisher(DocumentPublisherInterface):
    def __init__(self,
                 rabbitmq_client: RabbitmqClient):
        self.rabbitmq_client = rabbitmq_client
        self.queue = environment_variables.queue
        self.exchange = environment_variables.exchange

    def publish_document(self,
                         document_id: int) -> None:
        try:
            message = {
                "document_id": document_id
            }

            self.rabbitmq_client.publish(
                message,
                routing_key=self.queue,
                exchange=self.exchange)

            logger.info(
                "Published document event",
                extra={"document_id": document_id}
            )
        except Exception as e:
            logger.exception("Failed to publish document event")
            raise MessagingError("Failed to publish document message") from e