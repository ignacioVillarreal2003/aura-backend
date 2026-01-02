from app.application.exceptions.app_exceptions import AppError


class ContextProviderError(AppError):
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


class ContextRetrievalByQuestionError(ContextProviderError):
    def __init__(self,
                 message: str = "No se pudo recuperar el contexto basado en la pregunta proporcionada",
                 *,
                 code: str | None = None):
        super().__init__(
            message=message,
            code=code
        )


class ContextRetrievalByDocumentError(ContextProviderError):
    def __init__(self,
                 message: str = "No se pudo recuperar el contexto del documento especificado",
                 *,
                 code: str | None = None):
        super().__init__(
            message=message,
            code=code
        )
