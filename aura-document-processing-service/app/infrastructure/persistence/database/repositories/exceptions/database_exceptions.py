from app.application.exceptions.app_exception import AppException


class DatabaseException(AppException):
    pass


class DatabaseConstraintViolationException(DatabaseException):
    pass
