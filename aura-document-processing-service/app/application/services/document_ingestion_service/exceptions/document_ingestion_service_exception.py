from app.application.exceptions.app_exception import AppException


class DocumentIngestionServiceException(AppException):
    pass


class DocumentReadException(DocumentIngestionServiceException):
    pass


class DocumentCleanException(DocumentIngestionServiceException):
    pass


class DocumentSplitException(DocumentIngestionServiceException):
    pass


class DocumentEmbedException(DocumentIngestionServiceException):
    pass


class DocumentPersistenceException(DocumentIngestionServiceException):
    pass


class DocumentProcessingException(DocumentIngestionServiceException):
    pass


class InvalidConfigurationException(DocumentIngestionServiceException):
    pass
