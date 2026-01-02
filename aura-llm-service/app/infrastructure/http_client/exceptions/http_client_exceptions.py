from app.application.exceptions.app_exceptions import AppError


class HttpClientError(AppError):
    def __init__(self,
                 message: str = "La operación del cliente HTTP falló",
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
                 message: str = "Error al inicializar el cliente HTTP",
                 *,
                 code: str | None = None):
        super().__init__(
            message=message,
            code=code
        )


class HttpClientNotInitializedError(HttpClientError):
    def __init__(self,
                 message: str = "El cliente HTTP no está inicializado",
                 *,
                 code: str | None = None):
        super().__init__(
            message=message,
            code=code
        )


class ExternalServiceError(HttpClientError):
    def __init__(self,
                 *,
                 status_code: int,
                 message: str = "El servicio externo devolvió una respuesta de error",
                 code: str | None = None):
        super().__init__(
            message=message,
            status_code=status_code,
            code=code
        )


class NetworkError(HttpClientError):
    def __init__(self,
                 message: str = "Se produjo un error de red al realizar la solicitud HTTP",
                 *,
                 code: str | None = None):
        super().__init__(
            message=message,
            status_code=503,
            code=code
        )
