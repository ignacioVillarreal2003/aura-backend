from app.application.exceptions.app_exceptions import AppError


class DocumentContextProviderError(AppError):
    def __init__(self,
                 message: str = "La operación del proveedor de contexto falló",
                 *,
                 status_code: int = 500,
                 code: str | None = None):
        super().__init__(
            message=message,
            status_code=status_code,
            code=code,
        )
