from app.application.exceptions.app_exception import AppException


class DatabaseManagerException(AppException):
    pass


class DatabaseNotInitializedException(DatabaseManagerException):
    pass
