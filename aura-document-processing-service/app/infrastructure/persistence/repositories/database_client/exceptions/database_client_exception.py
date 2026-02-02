class DatabaseClientError(Exception):
    def __init__(self, message: str = "Database client operation failed", *, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class DatabaseClientNotInitializedError(DatabaseClientError):
    def __init__(self, message: str = "Database client not initialized"):
        super().__init__(message, status_code=500)


class DatabaseConnectionError(DatabaseClientError):
    def __init__(self, message: str = "Database connection failed"):
        super().__init__(message, status_code=500)


class DatabaseSessionError(DatabaseClientError):
    def __init__(self, message: str = "Database session error"):
        super().__init__(message, status_code=500)