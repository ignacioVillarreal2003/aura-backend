from app.application.exceptions.app_exceptions import AppError


class OllamaLLMFacadeError(AppError):
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


class LLMInitializationError(OllamaLLMFacadeError):
    def __init__(self,
                 message: str = "El LLM no pudo ser inicializado",
                 *,
                 code: str | None = None):
        super().__init__(
            message=message,
            code=code
        )


class LLMNotConfiguredError(LLMInitializationError):
    def __init__(self,
                 message: str = "El LLM no está configurado o inicializado",
                 *,
                 code: str | None = None):
        super().__init__(
            message=message,
            code=code
        )


class ToolInitializationError(OllamaLLMFacadeError):
    def __init__(self,
                 message: str = "Error al inicializar las herramientas",
                 *,
                 code: str | None = None):
        super().__init__(
            message=message,
            code=code
        )
