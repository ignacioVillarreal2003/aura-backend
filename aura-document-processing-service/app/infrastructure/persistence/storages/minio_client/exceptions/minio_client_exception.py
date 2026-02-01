class MinioClientError(Exception):
    def __init__(self, message: str = "Minio client operation failed", *, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class MinioClientNotInitializedError(MinioClientError):
    def __init__(self, message: str = "Minio client not initialized"):
        super().__init__(message, status_code=500)


class MinioConnectionError(MinioClientError):
    def __init__(self, message: str = "Minio connection failed"):
        super().__init__(message, status_code=500)


class MinioBucketError(MinioClientError):
    def __init__(self, message: str = "Minio bucket operation failed"):
        super().__init__(message, status_code=500)


class MinioObjectError(MinioClientError):
    def __init__(self, message: str = "Minio object operation failed"):
        super().__init__(message, status_code=500)
