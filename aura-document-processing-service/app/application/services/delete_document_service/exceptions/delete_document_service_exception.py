from app.application.exceptions.app_exception import AppException


class DeleteDocumentServiceException(AppException):
    pass


class DeleteDocumentNotFoundException(DeleteDocumentServiceException):
    pass


class DeleteDocumentUnauthorizedException(DeleteDocumentServiceException):
    pass


class DeleteDocumentFailedException(DeleteDocumentServiceException):
    pass


class DeleteFragmentsFailedException(DeleteDocumentServiceException):
    pass


class DeleteDocumentStorageException(DeleteDocumentServiceException):
    pass
