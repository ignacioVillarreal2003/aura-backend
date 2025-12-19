from app.application.exceptions.app_exceptions import AppError


class OllamaConfiguratorError(AppError):
    def __init__(self,
                 message: str = "Error en la operación del LLM",
                 *,
                 code: str | None = None):
        super().__init__(
            message,
            status_code=500,
            code=code,
        )


class LLMInitializationError(OllamaConfiguratorError):
    def __init__(self,
                 message: str = "No se pudo inicializar el LLM",
                 *,
                 code: str | None = None):
        super().__init__(message, code=code)


class LLMInvocationError(OllamaConfiguratorError):
    def __init__(self,
                 message: str = "Error al invocar el LLM",
                 *,
                 code: str | None = None):
        super().__init__(message, code=code)


class LLMNotConfiguredError(LLMInitializationError):
    def __init__(self,
                 message: str = "",
                 *,
                 code: str | None = None):
        super().__init__(message, code=code)
