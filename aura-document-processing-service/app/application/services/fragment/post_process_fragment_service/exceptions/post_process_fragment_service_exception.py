from app.application.exceptions.app_exception import AppException


class PostProcessFragmentServiceException(AppException):
    pass


class PostProcessFragmentAlreadyRunningException(PostProcessFragmentServiceException):
    pass


class PostProcessFragmentNotRunningException(PostProcessFragmentServiceException):
    pass


class PostProcessFragmentFailedException(PostProcessFragmentServiceException):
    pass


class PostProcessFragmentUnauthorizedException(PostProcessFragmentServiceException):
    pass


class PostProcessFragmentInvalidRequestException(PostProcessFragmentServiceException):
    pass
