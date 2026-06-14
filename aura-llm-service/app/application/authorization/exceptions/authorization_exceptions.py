from app.application.exceptions.app_exception import AppException


class AuthorizationException(AppException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=403)


class UnauthorizedException(AuthorizationException):
    def __init__(self, message: str) -> None:
        super().__init__(message)
