class DocumentStorageError(Exception):
    def __init__(self, message: str = "Document storage operation failed", *, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class DocumentUploadError(DocumentStorageError):
    def __init__(self, message: str = "Failed to upload document"):
        super().__init__(message, status_code=500)


class DocumentDownloadError(DocumentStorageError):
    def __init__(self, message: str = "Failed to download document"):
        super().__init__(message, status_code=404)


class DocumentDeleteError(DocumentStorageError):
    def __init__(self, message: str = "Failed to delete document"):
        super().__init__(message, status_code=500)
