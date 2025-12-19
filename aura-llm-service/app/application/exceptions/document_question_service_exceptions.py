from app.application.exceptions.app_exceptions import AppError


class DocumentQuestionServiceError(AppError):
    def __init__(self,
                 message: str = "Error en el servicio de preguntas sobre documentos",
                 *,
                 code: str | None = None):
        super().__init__(
            message,
            status_code=500,
            code=code,
        )


class ContextRetrievalError(DocumentQuestionServiceError):
    def __init__(self,
                 message: str = "Error al recuperar el contexto del documento",
                 *,
                 code: str | None = None):
        super().__init__(message, code=code)
