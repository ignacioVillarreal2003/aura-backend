from app.application.exceptions.app_exception import AppException


class DatabaseManagerException(AppException):
    pass


class DatabaseNotInitializedException(DatabaseManagerException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)


class DatabaseSessionException(DatabaseManagerException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)
