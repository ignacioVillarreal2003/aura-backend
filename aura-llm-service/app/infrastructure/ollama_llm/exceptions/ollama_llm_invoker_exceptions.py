from app.application.exceptions.app_exceptions import AppError


class OllamaLLMInvokerError(AppError):
    def __init__(self,
                 message: str = "Error en la operación del LLM",
                 *,
                 status_code: int = 500,
                 code: str | None = None):
        super().__init__(
            message=message,
            status_code=status_code,
            code=code
        )


class LLMInvocationError(OllamaLLMInvokerError):
    def __init__(self,
                 message: str = "Error al invocar el LLM",
                 *,
                 code: str | None = None):
        super().__init__(
            message=message,
            code=code
        )
