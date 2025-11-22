class AppError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code or self.__class__.__name__

class LLMError(AppError):
    def __init__(self, message: str = "Error en la operación del LLM", *, code: str | None = None):
        super().__init__(message, status_code=500, code=code)

class ConfigError(AppError):
    def __init__(self, message: str = "Error de configuración", *, code: str | None = None):
        super().__init__(message, status_code=500, code=code)

class MessagingError(AppError):
    def __init__(self, message: str = "Error en las colas", *, code: str | None = None):
        super().__init__(message, status_code=502, code=code)
