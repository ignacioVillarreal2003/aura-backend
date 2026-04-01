from app.application.exceptions.app_exception import AppException


class AuthenticationProviderException(AppException):
    pass


class AuthenticationProviderInvalidTokenException(AuthenticationProviderException):
    pass


class AuthenticationProviderUnauthorizedException(AuthenticationProviderException):
    pass


class AuthenticationProviderUserNotFoundException(AuthenticationProviderException):
    pass


class AuthenticationProviderServiceUnavailableException(AuthenticationProviderException):
    pass
