from app.application.exceptions.app_exception import AppException


class BulkDispatchServiceException(AppException):
    pass


class BulkOperationConflictException(BulkDispatchServiceException):
    pass


class BulkOperationUnavailableException(BulkDispatchServiceException):
    pass
