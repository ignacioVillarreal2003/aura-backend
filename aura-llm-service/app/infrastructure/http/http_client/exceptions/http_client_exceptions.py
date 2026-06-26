from app.application.exceptions.app_exception import AppException


class HttpClientException(AppException):
    pass


class HttpClientServerException(HttpClientException):
    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message, status_code=status_code)


class HttpClientNotStartedException(HttpClientException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)


class HttpClientConnectionException(HttpClientException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)


class HttpClientTimeoutException(HttpClientException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=504)


class HttpClientCircuitBreakerException(HttpClientException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)
