from app.application.exceptions.app_exception import AppException


class DocumentQueryServiceException(AppException):
    pass


class DocumentNotFoundError(DocumentQueryServiceException):
    pass


class DocumentQueryException(DocumentQueryServiceException):
    pass


class InvalidPaginationException(DocumentQueryServiceException):
    pass
