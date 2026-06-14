from app.application.exceptions.app_exception import AppException


class Neo4jManagerException(AppException):
    def __init__(self, message: str, *, status_code: int = 503) -> None:
        super().__init__(message, status_code=status_code)


class Neo4jNotStartedException(Neo4jManagerException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)


class Neo4jConnectionException(Neo4jManagerException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)


class Neo4jSchemaInitializationException(Neo4jManagerException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)
