import io
import logging
import os
import platform
import shutil
from pathlib import Path
from zipfile import ZipFile

import pytesseract
from PIL import Image

from app.application.processors.readers.exceptions.reader_exception import (
    ReaderFileNotFoundException,
    UnsupportedScannedDOCXFormatException,
    ScannedDOCXOCRExtractionException,
    ScannedDOCXReadException
)
from app.application.processors.readers.interfaces.reader_adapter_interface import DocumentReaderInterface

logger = logging.getLogger(__name__)


class ScannedDOCXReaderAdapter(DocumentReaderInterface):
    def __init__(
            self,
            lang: str = "spa"
    ):
        self.lang = lang
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
            raise ReaderFileNotFoundException(str(file_path))

        if not self.can_handle(file_path):
            raise UnsupportedScannedDOCXFormatException(file_path.suffix)

        logger.info(f"Reading scanned DOCX [file={file_path.name}, lang={self.lang}]")

        all_text = []
        try:
            images = self._extract_images_from_docx(file_path)

            logger.info(f"Extracted images from DOCX [file={file_path.name}, images={len(images)}]")

            for i, image in enumerate(images, start=1):
                try:
                    text = pytesseract.image_to_string(image, lang=self.lang)
                    if text.strip():
                        all_text.append(text.strip())
                except Exception as e:
                    logger.warning(f"OCR failed for image {i} in DOCX — skipping [reason={e}]")

            if not all_text:
                raise ScannedDOCXOCRExtractionException()

            logger.info(
                f"Scanned DOCX read successfully [file={file_path.name}, images_with_text={len(all_text)}/{len(images)}]"
            )
            return "\n\n".join(all_text)

        except (ReaderFileNotFoundException, UnsupportedScannedDOCXFormatException, ScannedDOCXOCRExtractionException):
            raise
        except Exception as e:
            raise ScannedDOCXReadException(str(file_path), e)

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
