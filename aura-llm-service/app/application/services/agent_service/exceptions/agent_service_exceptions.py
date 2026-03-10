from app.application.exceptions.app_exceptions import AppError


class AgentServiceError(AppError):
    def __init__(self,
                 message: str = "Error en el servicio de agente",
                 *,
                 status_code: int = 500,
                 code: str | None = None):
        super().__init__(
            message=message,
            status_code=status_code,
            code=code
        )
