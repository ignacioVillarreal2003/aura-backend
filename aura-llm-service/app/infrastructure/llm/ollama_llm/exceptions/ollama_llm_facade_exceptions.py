from app.application.exceptions.app_exception import AppException


class OllamaLLMFacadeError(AppException):
    pass


class LLMInitializationError(OllamaLLMFacadeError):
    pass


class LLMNotConfiguredError(LLMInitializationError):
    pass


class ToolInitializationError(OllamaLLMFacadeError):
    pass
