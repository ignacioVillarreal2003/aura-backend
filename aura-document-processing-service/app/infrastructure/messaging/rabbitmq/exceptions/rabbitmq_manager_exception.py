from app.application.exceptions.app_exception import AppException


class RabbitMQManagerException(AppException):
    pass


class RabbitMQNotStartedException(RabbitMQManagerException):
    pass


class RabbitMQConnectionException(RabbitMQManagerException):
    pass


class RabbitMQPublishException(RabbitMQManagerException):
    pass


class RabbitMQConsumerException(RabbitMQManagerException):
    pass


class RabbitMQTopologyException(RabbitMQManagerException):
    pass
