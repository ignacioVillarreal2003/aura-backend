from app.application.exceptions.app_exception import AppException


class TextSplitterException(AppException):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message, status_code=status_code)


class UnsupportedTextSplitterTypeException(TextSplitterException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class TextSplitterInitializationException(TextSplitterException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)


class TextSplitterExecutionException(TextSplitterException):
    pass


class TextSplitterUnavailableException(TextSplitterException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)
