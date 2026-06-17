from abc import ABC

from app.infrastructure.messaging.rabbitmq.consumer.interfaces.consumer_interface import ConsumerInterface


class DocumentReprocessConsumerInterface(ConsumerInterface, ABC):
    pass
