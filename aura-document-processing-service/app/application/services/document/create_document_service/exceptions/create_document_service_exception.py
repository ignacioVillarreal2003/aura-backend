from app.application.exceptions.app_exception import AppException


class CreateDocumentServiceException(AppException):
    pass


class CreateDocumentValidationException(CreateDocumentServiceException):
    pass


class CreateDocumentUploadException(CreateDocumentServiceException):
    pass


class CreateDocumentPersistenceException(CreateDocumentServiceException):
    pass


class CreateDocumentUnsupportedTypeException(CreateDocumentValidationException):
    pass


class CreateDocumentSizeExceededException(CreateDocumentValidationException):
    pass


class CreateDocumentInvalidException(CreateDocumentValidationException):
    pass
