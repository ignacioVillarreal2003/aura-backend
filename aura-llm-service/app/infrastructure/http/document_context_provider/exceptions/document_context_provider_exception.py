from app.application.exceptions.app_exception import AppException


class DocumentContextProviderError(AppException):
    pass


class DocumentContextProviderTimeoutException(DocumentContextProviderError):
    pass


class DocumentContextProviderUnavailableException(DocumentContextProviderError):
    pass


class DocumentContextProviderInvalidResponseException(DocumentContextProviderError):
    pass


class DocumentContextProviderUnauthorizedException(DocumentContextProviderError):
    pass
