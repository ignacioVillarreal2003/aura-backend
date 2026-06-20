from app.application.exceptions.app_exception import AppException


class MinioManagerException(AppException):
    pass


class MinioConnectionException(MinioManagerException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)


class MinioManagerNotInitializedException(MinioManagerException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)


class MinioBucketException(MinioManagerException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=502)


class MinioOperationException(MinioManagerException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=502)


class MinioUploadException(MinioOperationException):
    pass


class MinioDownloadException(MinioOperationException):
    pass


class MinioDeleteException(MinioOperationException):
    pass
