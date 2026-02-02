import io
import os
import platform
import shutil
from pathlib import Path
from zipfile import ZipFile

import pytesseract
from PIL import Image

from app.application.processors.readers.exceptions.reader_exception import (
    ReaderFileNotFoundError,
    UnsupportedScannedDOCXFormatError,
    ScannedDOCXOCRExtractionError,
    ScannedDOCXReadError
)
from app.application.processors.readers.interfaces.reader_adapter_interface import DocumentReaderInterface


class ScannedDOCXReaderAdapter(DocumentReaderInterface):
    def __init__(
            self
    ):
        self.tesseract_path = None

        if not self.tesseract_path:
            self.tesseract_path = shutil.which("tesseract")

        if platform.system() == "Windows":
            if not self.tesseract_path:
                default_tess = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
                if os.path.exists(default_tess):
                    self.tesseract_path = default_tess

        if self.tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_path

    def can_handle(
            self,
            file_path: Path
    ) -> bool:
        return file_path.suffix.lower() == ".docx"

    def read(
            self,
            file_path: Path
    ) -> str:
        if not file_path.exists():
            raise ReaderFileNotFoundError(str(file_path))

        if not self.can_handle(file_path):
            raise UnsupportedScannedDOCXFormatError(file_path.suffix)

        all_text = []
        try:
            images = self._extract_images_from_docx(file_path)
            
            for i, image in enumerate(images, start=1):
                text = pytesseract.image_to_string(image, lang="spa")
                if text.strip():
                    all_text.append(text.strip())

            if not all_text:
                raise ScannedDOCXOCRExtractionError()

            return "\n\n".join(all_text)

        except ScannedDOCXOCRExtractionError:
            raise
        except Exception as e:
            raise ScannedDOCXReadError(str(file_path), e)

    def _extract_images_from_docx(
            self,
            file_path: Path
    ) -> list:
        images = []
        with ZipFile(file_path, 'r') as docx_zip:
            for file_name in docx_zip.namelist():
                if file_name.startswith('word/media/') and file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif')):
                    image_data = docx_zip.read(file_name)
                    image = Image.open(io.BytesIO(image_data))
                    images.append(image)
        return images
