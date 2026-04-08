from app.application.exceptions.app_exception import AppException


class OllamaLLMInvokerError(AppException):
    pass


class LLMInvocationError(OllamaLLMInvokerError):
    pass
