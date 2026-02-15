from app.application.exceptions.app_exception import AppException


class HttpClientException(AppException):
    pass


class HttpClientNotStartedException(HttpClientException):
    pass


class HttpClientConnectionException(HttpClientException):
    pass


class HttpClientTimeoutException(HttpClientException):
    pass


class HttpClientCircuitBreakerException(HttpClientException):
    pass


class HttpClientConfigurationException(HttpClientException):
    pass


class HttpClientRetryException(HttpClientException):
    pass
