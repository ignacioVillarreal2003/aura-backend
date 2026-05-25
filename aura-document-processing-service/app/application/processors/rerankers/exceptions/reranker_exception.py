from app.application.exceptions.app_exception import AppException


class RerankerException(AppException):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message, status_code=status_code)


class UnsupportedRerankerTypeException(RerankerException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class RerankerInitializationException(RerankerException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)


class RerankerExecutionException(RerankerException):
    pass
