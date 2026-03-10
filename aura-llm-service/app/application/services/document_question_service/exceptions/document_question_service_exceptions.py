from app.application.exceptions.app_exceptions import AppError


class DocumentQuestionServiceError(AppError):
    def __init__(self,
                 message: str = "Error en el servicio de preguntas sobre documentos",
                 *,
                 status_code: int = 500,
                 code: str | None = None):
        super().__init__(
            message=message,
            status_code=status_code,
            code=code
        )
