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


class ServiceAuthenticationRejected(Exception):
    """Raised during service-to-service header evaluation (FastAPI parity)."""

    def __init__(self, status_code: int, error: str, detail: str):
        self.status_code = status_code
        self.error = error
        self.detail = detail
        super().__init__(detail)
