from app.application.exceptions.app_exception import AppException


class ReaderException(AppException):
    pass


class UnsupportedReaderException(ReaderException):
    pass


class ReaderInitializationException(ReaderException):
    pass


class ReaderFileNotFoundException(ReaderException):
    pass


class DigitalDOCXReadException(ReaderException):
    pass


class DOCXHasNoExtractableTextException(ReaderException):
    pass


class DigitalPDFReadException(ReaderException):
    pass


class PDFHasNoExtractableTextException(ReaderException):
    pass


class UnsupportedScannedDOCXFormatException(ReaderException):
    pass


class ScannedDOCXOCRExtractionException(ReaderException):
    pass


class ScannedDOCXReadException(ReaderException):
    pass


class UnsupportedScannedPDFFormatException(ReaderException):
    pass


class ScannedPDFOCRExtractionException(ReaderException):
    pass


class ScannedPDFReadException(ReaderException):
    pass


class DoclingPDFInitializationException(ReaderInitializationException):
    pass


class UnsupportedDoclingPDFFormatException(ReaderException):
    pass


class DoclingPDFExtractionException(ReaderException):
    pass


class DoclingPDFReadException(ReaderException):
    pass


class DoclingExtractionException(ReaderException):
    pass


class DoclingInitializationException(ReaderException):
    pass


class DoclingReadException(ReaderException):
    pass


class UnsupportedDoclingFormatException(ReaderException):
    pass
