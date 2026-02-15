from app.application.exceptions.app_exception import AppException


class DocumentDeletionServiceException(AppException):
    pass


class DocumentNotFoundError(DocumentDeletionServiceException):
    pass


class DocumentDeletionException(DocumentDeletionServiceException):
    pass


class FragmentDeletionException(DocumentDeletionServiceException):
    pass


class StorageDeletionException(DocumentDeletionServiceException):
    pass
