from app.application.exceptions.app_exception import AppException


class DocumentCreationServiceException(AppException):
    pass


class DocumentValidationException(DocumentCreationServiceException):
    pass


class DocumentUploadException(DocumentCreationServiceException):
    pass


class DocumentPersistenceException(DocumentCreationServiceException):
    pass


class UnsupportedDocumentTypeError(DocumentValidationException):
    pass


class DocumentSizeExceededError(DocumentValidationException):
    pass


class InvalidDocumentError(DocumentValidationException):
    pass


class DocumentProcessingException(DocumentCreationServiceException):
    pass


class TempFileException(DocumentCreationServiceException):
    pass
