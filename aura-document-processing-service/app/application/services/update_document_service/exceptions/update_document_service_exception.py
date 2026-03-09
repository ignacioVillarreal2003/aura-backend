from app.application.exceptions.app_exception import AppException


class UpdateDocumentServiceException(AppException):
    pass


class UpdateDocumentNotFoundException(UpdateDocumentServiceException):
    pass


class UpdateDocumentUnauthorizedException(UpdateDocumentServiceException):
    pass


class UpdateDocumentFailedException(UpdateDocumentServiceException):
    pass
