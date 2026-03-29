from app.application.exceptions.app_exception import AppException


class DocumentIngestionServiceException(AppException):
    pass


class DocumentIngestionServiceReadException(DocumentIngestionServiceException):
    pass


class DocumentIngestionServiceCleanException(DocumentIngestionServiceException):
    pass


class DocumentIngestionServiceSplitException(DocumentIngestionServiceException):
    pass


class DocumentIngestionServiceEmbedException(DocumentIngestionServiceException):
    pass


class DocumentIngestionServicePersistenceException(DocumentIngestionServiceException):
    pass
