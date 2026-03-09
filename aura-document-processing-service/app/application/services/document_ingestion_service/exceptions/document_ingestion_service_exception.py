from app.application.exceptions.app_exception import AppException


class DocumentIngestionServiceException(AppException):
    pass


class DocumentIngestionReadException(DocumentIngestionServiceException):
    pass


class DocumentIngestionCleanException(DocumentIngestionServiceException):
    pass


class DocumentIngestionSplitException(DocumentIngestionServiceException):
    pass


class DocumentIngestionEmbedException(DocumentIngestionServiceException):
    pass


class DocumentIngestionPersistenceException(DocumentIngestionServiceException):
    pass
