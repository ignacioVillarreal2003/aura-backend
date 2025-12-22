from app.application.exceptions.app_exceptions import AppError


class OllamaConfiguratorError(AppError):
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


class LLMInitializationError(OllamaConfiguratorError):
    def __init__(self,
                 message: str = "The LLM could not be initialized",
                 *,
                 code: str | None = None):
        super().__init__(
            message=message,
            code=code or "LLMInitializationError"
        )


class LLMNotConfiguredError(LLMInitializationError):
    def __init__(self,
                 message: str = "LLM is not configured or initialized",
                 *,
                 code: str | None = None):
        super().__init__(
            message=message,
            code=code or "LLMNotConfiguredError"
        )


class ToolInitializationError(OllamaConfiguratorError):
    def __init__(self,
                 message: str = "Failed to initialize tools",
                 *,
                 code: str | None = None):
        super().__init__(
            message=message,
            code=code or "ToolInitializationError"
        )


class LLMInvocationError(OllamaConfiguratorError):
    def __init__(self,
                 message: str = "Error invoking the LLM",
                 *,
                 code: str | None = None):
        super().__init__(
            message=message,
            code=code or "LLMInvocationError"
        )
