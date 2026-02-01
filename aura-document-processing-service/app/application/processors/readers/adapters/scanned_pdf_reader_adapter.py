import os
import platform
import shutil
from pathlib import Path
from pdf2image import convert_from_path
import pytesseract

from app.application.processors.readers.exceptions.reader_exception import (
    ReaderFileNotFoundError,
    UnsupportedScannedPDFFormatError,
    ScannedPDFOCRExtractionError,
    ScannedPDFReadError
)
from app.application.processors.readers.interfaces.reader_adapter_interface import DocumentReaderInterface


class ScannedPDFReaderAdapter(DocumentReaderInterface):
    def __init__(
            self
    ):
        self.tesseract_path = None
        self.poppler_path = None

        if not self.tesseract_path:
            self.tesseract_path = shutil.which("tesseract")

        if platform.system() == "Windows":
            if not self.tesseract_path:
                default_tess = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
                if os.path.exists(default_tess):
                    self.tesseract_path = default_tess

            if not self.poppler_path:
                default_poppler = r"C:\Program Files\poppler-25.07.0\Library\bin"
                if os.path.exists(default_poppler):
                    self.poppler_path = default_poppler

        if self.tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_path

    def can_handle(
            self,
            file_path: Path
    ) -> bool:
        return file_path.suffix.lower() == ".pdf"

    def read(
            self,
            file_path: Path
    ) -> str:
        if not file_path.exists():
            raise ReaderFileNotFoundError(str(file_path))

        if not self.can_handle(file_path):
            raise UnsupportedScannedPDFFormatError(file_path.suffix)

        all_text = []
        try:
            pages = convert_from_path(str(file_path), dpi=300, poppler_path=self.poppler_path)

            for i, page in enumerate(pages, start=1):
                text = pytesseract.image_to_string(page, lang="spa")
                if text.strip():
                    all_text.append(text.strip())

            if not all_text:
                raise ScannedPDFOCRExtractionError()

            return "\n\n".join(all_text)

        except Exception as e:
            raise ScannedPDFReadError(str(file_path), e)
