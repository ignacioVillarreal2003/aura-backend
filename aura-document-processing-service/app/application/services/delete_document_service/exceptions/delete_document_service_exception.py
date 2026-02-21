from app.application.exceptions.app_exception import AppException


class DeleteDocumentServiceException(AppException):
    pass


class DocumentNotFoundError(DeleteDocumentServiceException):
    pass


class DocumentDeletionException(DeleteDocumentServiceException):
    pass


class FragmentDeletionException(DeleteDocumentServiceException):
    pass


class StorageDeletionException(DeleteDocumentServiceException):
    pass
