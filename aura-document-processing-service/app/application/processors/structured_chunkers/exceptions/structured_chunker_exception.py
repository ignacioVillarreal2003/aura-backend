class StructuredChunkerException(Exception):
    """Base error for the structured chunking subsystem."""


class StructuredChunkerInitializationException(StructuredChunkerException):
    """Raised when a structured chunker cannot be initialized."""


class StructuredChunkerExecutionException(StructuredChunkerException):
    """Raised when a structured chunker fails while chunking a document."""


class StructuredChunkerUnavailableException(StructuredChunkerException):
    """Raised when the structured chunker's optional dependencies are missing."""
