class AuthenticationProviderException(Exception):
    pass


class AuthenticationProviderInvalidTokenException(AuthenticationProviderException):
    pass


class AuthenticationProviderUnauthorizedException(AuthenticationProviderException):
    pass


class AuthenticationProviderUserNotFoundException(AuthenticationProviderException):
    pass


class AuthenticationProviderServiceUnavailableException(AuthenticationProviderException):
    pass


class ServiceAuthenticationRejected(AuthenticationProviderException):
    def __init__(self, status_code, error_code, detail):
        self.status_code = status_code
        self.error_code = error_code
        self.detail = detail
        super().__init__(detail)
