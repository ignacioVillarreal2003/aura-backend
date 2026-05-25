from app.application.exceptions.app_exception import AppException


class EmbedderException(AppException):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message, status_code=status_code)


class UnsupportedEmbedderTypeException(EmbedderException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class EmbedderInitializationException(EmbedderException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)


class EmbedDocumentsException(EmbedderException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=502)


class EmbedQueryException(EmbedderException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=502)
