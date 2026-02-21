from app.application.exceptions.app_exception import AppException


class ReaderException(AppException):
    pass


class UnsupportedReaderException(ReaderException):
    def __init__(self, file_path: str):
        super().__init__(
            f"No reader available for file: '{file_path}'",
            status_code=422
        )


class UnsupportedReaderError(ReaderException):
    def __init__(self, file_path: str = "unknown"):
        super().__init__(
            f"No reader available for file: '{file_path}'",
            status_code=422
        )


class ReaderFileNotFoundException(ReaderException):
    def __init__(self, file_path: str):
        super().__init__(
            f"File not found: '{file_path}'",
            status_code=404
        )


class UnsupportedDOCXFormatException(ReaderException):
    def __init__(self, suffix: str):
        super().__init__(
            f"Unsupported format for DOCX reader: '{suffix}'",
            status_code=422
        )


class DOCXReadException(ReaderException):
    def __init__(self, file_path: str, cause: Exception):
        super().__init__(
            f"Failed to read DOCX '{file_path}': {cause}",
            status_code=500
        )


class UnsupportedDigitalDOCXFormatException(ReaderException):
    def __init__(self, suffix: str):
        super().__init__(
            f"Unsupported format for digital DOCX reader: '{suffix}' — file has no extractable text",
            status_code=422
        )


class DigitalDOCXReadException(ReaderException):
    def __init__(self, file_path: str, cause: Exception):
        super().__init__(
            f"Failed to read digital DOCX '{file_path}': {cause}",
            status_code=500
        )


class DOCXHasNoExtractableTextException(ReaderException):
    def __init__(self):
        super().__init__(
            "DOCX has no extractable text — document may be empty or contain only images",
            status_code=422
        )


class UnsupportedScannedDOCXFormatException(ReaderException):
    def __init__(self, suffix: str):
        super().__init__(
            f"Unsupported format for scanned DOCX reader: '{suffix}'",
            status_code=422
        )


class ScannedDOCXOCRExtractionException(ReaderException):
    def __init__(self):
        super().__init__(
            "OCR produced no extractable text from DOCX — document may have no embedded images or low image quality",
            status_code=422
        )


class ScannedDOCXReadException(ReaderException):
    def __init__(self, file_path: str, cause: Exception):
        super().__init__(
            f"Failed to read scanned DOCX '{file_path}': {cause}",
            status_code=500
        )


class UnsupportedDigitalPDFFormatException(ReaderException):
    def __init__(self, suffix: str):
        super().__init__(
            f"Unsupported format for digital PDF reader: '{suffix}' — file has no extractable text",
            status_code=422
        )


class PDFHasNoExtractableTextException(ReaderException):
    def __init__(self):
        super().__init__(
            "PDF has no extractable text — document may be scanned or image-based",
            status_code=422
        )


class DigitalPDFReadException(ReaderException):
    def __init__(self, file_path: str, cause: Exception):
        super().__init__(
            f"Failed to read digital PDF '{file_path}': {cause}",
            status_code=500
        )


class UnsupportedScannedPDFFormatException(ReaderException):
    def __init__(self, suffix: str):
        super().__init__(
            f"Unsupported format for scanned PDF reader: '{suffix}'",
            status_code=422
        )


class ScannedPDFOCRExtractionException(ReaderException):
    def __init__(self):
        super().__init__(
            "OCR produced no extractable text from PDF — document may have no pages or very low image quality",
            status_code=422
        )


class ScannedPDFReadException(ReaderException):
    def __init__(self, file_path: str, cause: Exception):
        super().__init__(
            f"Failed to read scanned PDF '{file_path}': {cause}",
            status_code=500
        )
