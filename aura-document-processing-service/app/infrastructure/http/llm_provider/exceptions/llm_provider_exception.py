from app.application.exceptions.app_exception import AppException


class LlmProviderException(AppException):
    pass


class LlmProviderInvalidResponseException(LlmProviderException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=502)
