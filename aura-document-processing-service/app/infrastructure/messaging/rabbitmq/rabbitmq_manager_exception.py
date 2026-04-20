from app.application.exceptions.app_exception import AppException


class RabbitMQManagerException(AppException):
    pass


class RabbitMQNotStartedException(RabbitMQManagerException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)


class RabbitMQConnectionException(RabbitMQManagerException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)


class RabbitMQPublishException(RabbitMQManagerException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=502)


class RabbitMQConsumerException(RabbitMQManagerException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)


class RabbitMQTopologyException(RabbitMQManagerException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)
