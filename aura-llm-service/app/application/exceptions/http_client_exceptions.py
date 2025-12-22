from app.application.exceptions.app_exceptions import AppError


class HttpClientError(AppError):
    def __init__(self,
                 message: str = "HTTP client operation failed",
                 *,
                 status_code: int = 500,
                 code: str | None = None):
        super().__init__(
            message=message,
            status_code=status_code,
            code=code
        )


class HttpClientInitializationError(HttpClientError):
    def __init__(self,
                 message: str = "Failed to initialize HTTP client",
                 *,
                 code: str | None = None):
        super().__init__(
            message=message,
            status_code=500,
            code=code,
        )


class HttpClientNotInitializedError(HttpClientError):
    def __init__(self,
                 message: str = "HTTP client is not initialized",
                 *,
                 code: str | None = None):
        super().__init__(
            message=message,
            status_code=500,
            code=code
        )


class ExternalServiceError(HttpClientError):
    def __init__(self,
                 *,
                 status_code: int,
                 message: str = "External service returned an error response",
                 code: str | None = None):
        super().__init__(
            message=message,
            status_code=status_code,
            code=code
        )


class NetworkError(HttpClientError):
    def __init__(self,
                 message: str = "Network error occurred while performing HTTP request",
                 *,
                 code: str | None = None):
        super().__init__(
            message=message,
            status_code=503,
            code=code
        )
