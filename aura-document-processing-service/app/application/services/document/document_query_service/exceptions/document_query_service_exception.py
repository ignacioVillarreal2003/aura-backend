from app.application.exceptions.app_exception import AppException


class DocumentQueryServiceException(AppException):
    pass


class DocumentQueryNotFoundException(DocumentQueryServiceException):
    pass


class DocumentQueryUnauthorizedException(DocumentQueryServiceException):
    pass


class DocumentQueryInvalidRequestException(DocumentQueryServiceException):
    pass


class DocumentQueryEmbeddingException(DocumentQueryServiceException):
    pass


class DocumentQueryFragmentRetrievalException(DocumentQueryServiceException):
    pass
