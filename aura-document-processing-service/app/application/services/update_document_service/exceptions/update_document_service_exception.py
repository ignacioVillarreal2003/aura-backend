from app.application.exceptions.app_exception import AppException


class UpdateDocumentServiceException(AppException):
    pass


class DocumentNotFoundError(UpdateDocumentServiceException):
    pass


class DocumentUpdateException(UpdateDocumentServiceException):
    pass
