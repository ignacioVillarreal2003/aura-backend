class AppError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code or self.__class__.__name__


class ValidationError(AppError):
    def __init__(self, message: str = "Error de validación", *, code: str | None = None):
        super().__init__(message, status_code=422, code=code)


class NotFoundError(AppError):
    def __init__(self, message: str = "Recurso no encontrado", *, code: str | None = None):
        super().__init__(message, status_code=404, code=code)


class UnsupportedFileTypeError(AppError):
    def __init__(self, message: str = "Tipo de archivo no soportado", *, code: str | None = None):
        super().__init__(message, status_code=415, code=code)


class StorageError(AppError):
    def __init__(self, message: str = "Error en el almacenamiento", *, code: str | None = None):
        super().__init__(message, status_code=502, code=code)


class DatabaseError(AppError):
    def __init__(self, message: str = "Error en la base de datos", *, code: str | None = None):
        super().__init__(message, status_code=500, code=code)


class ConfigError(AppError):
    def __init__(self, message: str = "Error de configuración", *, code: str | None = None):
        super().__init__(message, status_code=500, code=code)


class MessagingError(AppError):
    def __init__(self, message: str = "Error en las colas", *, code: str | None = None):
        super().__init__(message, status_code=502, code=code)


class UnsupportedTextSplitterMethodError(AppError):
    def __init__(self, method: str, *, code: str | None = None):
        message = f"Método de text splitting no soportado: {method}"
        super().__init__(message, status_code=400, code=code)


class TextSplitterError(AppError):
    def __init__(self, message: str = "Error al generar splits de texto", *, code: str | None = None):
        super().__init__(message, status_code=500, code=code)


class UnsupportedTextCleanerMethodError(AppError):
    def __init__(self, method: str, *, code: str | None = None):
        message = f"Método de text cleaning no soportado: {method}"
        super().__init__(message, status_code=400, code=code)


class UnsupportedEmbedderMethodError(AppError):
    def __init__(self, method: str, *, code: str | None = None):
        message = f"Método de embedding no soportado: {method}"
        super().__init__(message, status_code=400, code=code)


class EmbedderError(AppError):
    def __init__(self, message: str = "Error al generar embeddings de texto", *, code: str | None = None):
        super().__init__(message, status_code=500, code=code)


class UnsupportedReaderError(AppError):
    def __init__(self, *, code: str | None = None):
        message = "No se encontró lector compatible para el archivo"
        super().__init__(message, status_code=400, code=code)


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