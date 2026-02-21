from app.application.exceptions.app_exception import AppException


class CreateDocumentServiceException(AppException):
    pass


class DocumentValidationException(CreateDocumentServiceException):
    pass


class DocumentUploadException(CreateDocumentServiceException):
    pass


class DocumentPersistenceException(CreateDocumentServiceException):
    pass


class UnsupportedDocumentTypeError(DocumentValidationException):
    pass


class DocumentSizeExceededError(DocumentValidationException):
    pass


class InvalidDocumentError(DocumentValidationException):
    pass


class DocumentProcessingException(CreateDocumentServiceException):
    pass


class TempFileException(CreateDocumentServiceException):
    pass


class DocumentNotFoundException(CreateDocumentServiceException):
    pass


class DocumentAccessForbiddenException(CreateDocumentServiceException):
    pass
