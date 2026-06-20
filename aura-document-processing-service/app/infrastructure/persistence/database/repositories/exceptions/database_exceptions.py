from app.application.exceptions.app_exception import AppException


class DatabaseException(AppException):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message, status_code=status_code)


class DatabaseConstraintViolationException(DatabaseException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=409)
