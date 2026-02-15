from app.application.exceptions.app_exception import AppException


class DocumentStorageException(AppException):
    pass


class DocumentStorageError(DocumentStorageException):
    pass


class DocumentValidationError(DocumentStorageException):
    pass


class DocumentUploadError(DocumentStorageException):
    pass


class DocumentDownloadError(DocumentStorageException):
    pass


class DocumentDeleteError(DocumentStorageException):
    pass


class DocumentNotFoundError(DocumentStorageException):
    pass


class DocumentAccessError(DocumentStorageException):
    pass


class DocumentSizeLimitError(DocumentValidationError):
    pass


class DocumentExtensionError(DocumentValidationError):
    pass
