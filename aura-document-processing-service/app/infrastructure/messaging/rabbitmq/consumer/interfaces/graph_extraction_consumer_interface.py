from abc import ABC

from app.infrastructure.messaging.rabbitmq.consumer.interfaces.consumer_interface import ConsumerInterface


class GraphExtractionConsumerInterface(ConsumerInterface, ABC):
    pass
