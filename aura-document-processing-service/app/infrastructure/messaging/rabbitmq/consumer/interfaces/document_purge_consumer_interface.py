from abc import ABC

from app.infrastructure.messaging.rabbitmq.consumer.interfaces.consumer_interface import ConsumerInterface


class DocumentPurgeConsumerInterface(ConsumerInterface, ABC):
    pass
