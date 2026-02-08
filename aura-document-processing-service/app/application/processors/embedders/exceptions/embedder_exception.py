from app.application.exceptions.app_exception import AppException


class EmbedderError(AppException):
    def __init__(self,
                 message: str = "Error al generar embeddings de documentos",
                 *,
                 status_code: int = 500,
                 code: str | None = None):
        super().__init__(
            message=message,
            status_code=status_code,
            code=code,
        )


class UnsupportedEmbedderMethodError(EmbedderError):
    def __init__(self,
                 message: str = "Método de embedding no soportado",
                 *,
                 code: str | None = None):
        super().__init__(
            message=message,
            code=code
        )
