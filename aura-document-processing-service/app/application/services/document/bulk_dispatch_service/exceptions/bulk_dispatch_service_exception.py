class BulkDispatchServiceException(RuntimeError):
    """Base error for the bulk dispatch coordinator."""


class BulkOperationConflictException(BulkDispatchServiceException):
    """Raised when a bulk operation of the same kind is already running."""


class BulkOperationUnavailableException(BulkDispatchServiceException):
    """Raised when the publisher backing a requested operation is not available."""
