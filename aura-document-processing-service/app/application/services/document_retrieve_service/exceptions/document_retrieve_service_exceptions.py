from app.application.exceptions.app_exception import AppException


class DocumentContextServiceException(AppException):
    pass


class EmbeddingException(DocumentContextServiceException):
    pass


class FragmentRetrievalException(DocumentContextServiceException):
    pass


class InvalidQueryException(DocumentContextServiceException):
    pass
