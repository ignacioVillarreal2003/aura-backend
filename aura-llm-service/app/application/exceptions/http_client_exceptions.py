from app.application.exceptions.app_exceptions import AppError


class HttpClientError(AppError):
    def __init__(self,
                 message: str = "HTTP client error",
                 *,
                 status_code: int = 502,
                 code: str | None = None):
        super().__init__(
            message,
            status_code=status_code,
            code=code,
        )


class ClientNotInitializedError(HttpClientError):
    def __init__(self,
                 message: str = "HTTP client is not initialized",
                 *,
                 code: str | None = None):
        super().__init__(message, code=code)


class NetworkException(HttpClientError):
    def __init__(self,
                 message: str = "Network error communicating with external service",
                 *,
                 code: str | None = None):
        super().__init__(message, code=code)


class ExternalServiceException(HttpClientError):
    def __init__(self,
                 *,
                 status_code: int,
                 message: str,
                 url: str,
                 code: str | None = None):
        self.url = url
        super().__init__(
            message=f"External service at {url} failed: {message}",
            status_code=status_code,
            code=code or "ExternalServiceError",
        )
