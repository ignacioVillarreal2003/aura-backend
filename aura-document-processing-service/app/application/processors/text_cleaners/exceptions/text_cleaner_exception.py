from app.application.exceptions.app_exception import AppError


class TextCleanerError(AppError):
    def __init__(self,
                 message: str = "Error al generar leer el documento",
                 *,
                 status_code: int = 500,
                 code: str | None = None):
        super().__init__(
            message=message,
            status_code=status_code,
            code=code,
        )


class UnsupportedTextCleanerMethodError(TextCleanerError):
    def __init__(self,
                 message: str = "Método de text cleaning no soportado",
                 *,
                 code: str | None = 400):
        super().__init__(
            message=message,
            code=code
        )
