class HttpClientException(Exception):
    def __init__(self, message: str = "HTTP client error", status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


class HttpClientTimeoutException(HttpClientException):
    def __init__(self, message: str = "Request timed out"):
        super().__init__(message)


class HttpClientConnectionException(HttpClientException):
    def __init__(self, message: str = "Connection failed"):
        super().__init__(message)
