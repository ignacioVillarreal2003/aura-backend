from app.application.exceptions.app_exception import AppException


class DocumentStorageException(AppException):
    pass


class DocumentValidationException(DocumentStorageException):
    pass


class DocumentSizeLimitException(DocumentValidationException):
    pass


class DocumentExtensionException(DocumentValidationException):
    pass


class DocumentUploadException(DocumentStorageException):
    pass


class DocumentDownloadException(DocumentStorageException):
    pass


class DocumentDeleteException(DocumentStorageException):
    pass


class DocumentNotFoundException(DocumentStorageException):
    pass
