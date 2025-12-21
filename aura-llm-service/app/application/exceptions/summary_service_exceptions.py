from app.application.exceptions.app_exceptions import AppError


class SummaryServiceError(AppError):
    def __init__(self,
                 message: str = "Error en el servicio de resumen de documentos",
                 *,
                 code: str | None = None):
        super().__init__(
            message,
            status_code=500,
            code=code,
        )


class DocumentFragmentsRetrievalError(SummaryServiceError):
    def __init__(self,
                 message: str = "Error al recuperar los fragmentos del documento",
                 *,
                 code: str | None = None):
        super().__init__(message, code=code)


class SummaryGenerationError(SummaryServiceError):
    def __init__(self,
                 message: str = "Error al generar el resumen del documento",
                 *,
                 code: str | None = None):
        super().__init__(message, code=code)

