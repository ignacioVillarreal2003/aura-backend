from app.application.exceptions.app_exception import AppException


class HttpClientException(AppException):
    pass


class HttpClientConnectionException(HttpClientException):
    pass


class HttpClientTimeoutException(HttpClientException):
    pass


class HttpClientCircuitBreakerException(HttpClientException):
    pass