from app.application.exceptions.app_exception import AppException


class AuthenticationProviderException(AppException):
    def __init__(self, message: str, *, status_code: int = 503) -> None:
        super().__init__(message=message, status_code=status_code)


class AuthenticationProviderInvalidTokenException(AuthenticationProviderException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=401)


class AuthenticationProviderUnauthorizedException(AuthenticationProviderException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=403)


class AuthenticationProviderUserNotFoundException(AuthenticationProviderException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=404)


class AuthenticationProviderServiceUnavailableException(AuthenticationProviderException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)
