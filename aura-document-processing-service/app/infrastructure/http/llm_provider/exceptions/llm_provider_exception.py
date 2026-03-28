from app.application.exceptions.app_exception import AppException


class LlmProviderException(AppException):
    pass


class LlmProviderTimeoutException(LlmProviderException):
    pass


class LlmProviderUnavailableException(LlmProviderException):
    pass


class LlmProviderInvalidResponseException(LlmProviderException):
    pass
