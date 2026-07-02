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
