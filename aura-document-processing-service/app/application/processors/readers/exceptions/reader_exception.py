from app.application.exceptions.app_exception import AppException


class ReaderException(AppException):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message, status_code=status_code)


class UnsupportedReaderException(ReaderException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=415)


class ReaderInitializationException(ReaderException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)


class ReaderFileNotFoundException(ReaderException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=404)


class UnsupportedReaderFormatException(ReaderException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=415)


class DigitalDOCXReadException(ReaderException):
    pass


class DOCXHasNoExtractableTextException(ReaderException):
    pass


class DigitalPDFReadException(ReaderException):
    pass


class PDFHasNoExtractableTextException(ReaderException):
    pass


class UnsupportedScannedDOCXFormatException(UnsupportedReaderFormatException):
    pass


class ScannedDOCXOCRExtractionException(ReaderException):
    pass


class ScannedDOCXReadException(ReaderException):
    pass


class UnsupportedScannedPDFFormatException(UnsupportedReaderFormatException):
    pass


class ScannedPDFOCRExtractionException(ReaderException):
    pass


class ScannedPDFReadException(ReaderException):
    pass


class DoclingExtractionException(ReaderException):
    pass


class DoclingInitializationException(ReaderInitializationException):
    pass


class DoclingReadException(ReaderException):
    pass


class UnsupportedDoclingFormatException(UnsupportedReaderFormatException):
    pass


class PlainTextReadException(ReaderException):
    pass


class PlainTextHasNoContentException(ReaderException):
    pass


class CSVReadException(ReaderException):
    pass


class CSVHasNoContentException(ReaderException):
    pass
