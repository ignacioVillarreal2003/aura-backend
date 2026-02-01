from app.application.exceptions.app_exception import AppError


class ReaderError(AppError):
    def __init__(self,
                 message: str = "Error al generar leer el documento",
                 *,
                 status_code: int = 500,
                 code: str | None = None):
        super().__init__(
            message=message,
            status_code=status_code,
            code=code,
        )


class UnsupportedReaderError(ReaderError):
    def __init__(self,
                 message: str = "No se encontró lector compatible para el archivo",
                 *,
                 code: str | None = 400):
        super().__init__(
            message=message,
            code=code
        )

class ReaderFileNotFoundError(AppError):
    def __init__(self, file_path: str, *, code: str | None = None):
        message = f"El archivo no existe: {file_path}"
        super().__init__(message, status_code=404, code=code)


class UnsupportedDOCXFormatError(AppError):
    def __init__(self, extension: str, *, code: str | None = None):
        message = f"Formato no soportado por DOCXReader: {extension}"
        super().__init__(message, status_code=415, code=code)


class DOCXReadError(AppError):
    def __init__(self, file_path: str, original: Exception, *, code: str | None = None):
        message = f"Error al leer el archivo DOCX {file_path}: {original}"
        super().__init__(message, status_code=500, code=code)


class UnsupportedDigitalPDFFormatError(AppError):
    def __init__(self, extension: str, *, code: str | None = None):
        message = f"Formato no soportado por PDFReaderDigital: {extension}"
        super().__init__(message, status_code=415, code=code)


class PDFHasNoExtractableTextError(AppError):
    def __init__(self, *, code: str | None = None):
        message = "El PDF no contiene texto extraíble."
        super().__init__(message, status_code=422, code=code)


class DigitalPDFReadError(AppError):
    def __init__(self, file_path: str, original: Exception, *, code: str | None = None):
        message = f"Error al leer el archivo PDF {file_path}: {original}"
        super().__init__(message, status_code=500, code=code)


class UnsupportedScannedPDFFormatError(AppError):
    def __init__(self, extension: str, *, code: str | None = None):
        message = f"Formato no soportado por PDFReaderScanned: {extension}"
        super().__init__(message, status_code=415, code=code)


class ScannedPDFOCRExtractionError(AppError):
    def __init__(self, *, code: str | None = None):
        message = "No se extrajo texto mediante OCR."
        super().__init__(message, status_code=422, code=code)


class ScannedPDFReadError(AppError):
    def __init__(self, file_path: str, original: Exception, *, code: str | None = None):
        message = f"Error al aplicar OCR al archivo PDF {file_path}. Error: {original}"
        super().__init__(message, status_code=500, code=code)