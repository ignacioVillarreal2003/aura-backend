from app.application.exceptions.app_exception import AppException


class PostProcessDocumentServiceException(AppException):
    pass


class PostProcessAlreadyRunningException(PostProcessDocumentServiceException):
    pass


class PostProcessNotRunningException(PostProcessDocumentServiceException):
    pass


class PostProcessDocumentFailedException(PostProcessDocumentServiceException):
    pass
