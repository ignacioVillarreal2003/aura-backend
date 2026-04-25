from app.application.exceptions.app_exception import AppException


class TextCleanerException(AppException):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message, status_code=status_code)


class UnsupportedTextCleanerTypeException(TextCleanerException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=415)


class TextCleanerInitializationException(TextCleanerException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)


class TextCleanerExecutionException(TextCleanerException):
    pass
