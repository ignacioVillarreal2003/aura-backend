from app.application.exceptions.app_exception import AppException


class RetrieveDocumentServiceException(AppException):
    pass


class EmbeddingException(RetrieveDocumentServiceException):
    pass


class FragmentRetrievalException(RetrieveDocumentServiceException):
    pass


class InvalidQueryException(RetrieveDocumentServiceException):
    pass
