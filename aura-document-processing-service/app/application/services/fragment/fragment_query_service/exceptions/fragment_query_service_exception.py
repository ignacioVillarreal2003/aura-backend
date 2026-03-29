from app.application.exceptions.app_exception import AppException


class FragmentQueryServiceException(AppException):
    pass


class FragmentQueryNotFoundException(FragmentQueryServiceException):
    pass


class FragmentQueryUnauthorizedException(FragmentQueryServiceException):
    pass


class FragmentQueryInvalidRequestException(FragmentQueryServiceException):
    pass


class FragmentQueryEmbeddingException(FragmentQueryServiceException):
    pass


class FragmentQueryRetrievalException(FragmentQueryServiceException):
    pass
