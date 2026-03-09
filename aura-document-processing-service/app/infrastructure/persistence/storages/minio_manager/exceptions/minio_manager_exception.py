from app.application.exceptions.app_exception import AppException


class MinioManagerException(AppException):
    pass


class MinioConnectionException(MinioManagerException):
    pass


class MinioManagerNotInitializedException(MinioManagerException):
    pass


class MinioBucketException(MinioManagerException):
    pass


class MinioOperationException(MinioManagerException):
    pass


class MinioUploadException(MinioOperationException):
    pass


class MinioDownloadException(MinioOperationException):
    pass


class MinioDeleteException(MinioOperationException):
    pass
