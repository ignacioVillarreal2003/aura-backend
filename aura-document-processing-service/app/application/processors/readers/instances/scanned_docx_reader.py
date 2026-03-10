import io
import logging
from pathlib import Path
from typing import List
from zipfile import ZipFile
import pytesseract
from PIL import Image

from app.application.processors.readers.exceptions.reader_exception import (
    ReaderFileNotFoundException,
    ScannedDOCXOCRExtractionException,
    ScannedDOCXReadException,
    UnsupportedScannedDOCXFormatException
)
from app.application.processors.readers.interfaces.reader_interface import ReaderInterface
from app.application.processors.readers.reader_settings import ReaderSettings

logger = logging.getLogger(__name__)


class ScannedDOCXReader(ReaderInterface):
    def __init__(
            self,
            reader_settings: ReaderSettings
    ) -> None:
        self._reader_settings = reader_settings

        if not reader_settings.tesseract_path:
            raise RuntimeError("Tesseract not found. Install tesseract-ocr or set READER_TESSERACT_PATH")

        pytesseract.pytesseract.tesseract_cmd = reader_settings.tesseract_path

    def can_handle(
            self,
            file_path: Path
    ) -> bool:
        if file_path.suffix.lower() != ".docx":
            return False

        if not self._is_valid_docx(file_path):
            return False

        return self._has_images(file_path)

    def read(
            self,
            file_path: Path
    ) -> str:
        if not file_path.exists():
            raise ReaderFileNotFoundException("The specified DOCX file does not exist or cannot be accessed.")

        if not self.can_handle(file_path):
            raise UnsupportedScannedDOCXFormatException("The DOCX file is not a supported scanned document format for OCR processing.")

        logger.info(
            "Reading scanned DOCX",
            extra={
                "file": file_path.name,
                "lang": self._reader_settings.tesseract_lang
            }
        )

        all_text = []
        images: List[Image.Image] = []

        try:
            images = self._extract_images_from_docx(file_path)

            logger.info(
                "Extracted images from DOCX",
                extra={
                    "file": file_path.name,
                    "images": len(images)
                }
            )

            for i, image in enumerate(images, start=1):
                try:
                    text = pytesseract.image_to_string(
                        image,
                        lang=self._reader_settings.tesseract_lang,
                        timeout=self._reader_settings.tesseract_timeout
                    )
                    if text.strip():
                        all_text.append(text.strip())

                except pytesseract.TesseractError as e:
                    logger.warning(
                        "Tesseract error on image",
                        extra={
                            "image_num": i,
                            "error": str(e)
                        }
                    )
                except RuntimeError as e:
                    if "timeout" in str(e).lower():
                        logger.warning(
                            "OCR timeout on image",
                            extra={
                                "image_num": i,
                                "timeout": self._reader_settings.tesseract_timeout
                            }
                        )
                    else:
                        raise
                except Exception as e:
                    logger.warning(
                        "OCR failed for image — skipping",
                        extra={
                            "image_num": i,
                            "error": str(e)
                        }
                    )

            if not all_text:
                raise ScannedDOCXOCRExtractionException("OCR processing completed but no extractable text was found in the scanned DOCX file.")

            logger.info(
                "Scanned DOCX read successfully",
                extra={
                    "file": file_path.name,
                    "images_with_text": len(all_text)
                }
            )

            return "\n\n".join(all_text)

        except (
                ReaderFileNotFoundException,
                UnsupportedScannedDOCXFormatException,
                ScannedDOCXOCRExtractionException
        ):
            raise
        except Exception as e:
            logger.exception(
                "Error reading scanned DOCX",
                extra={
                    "file": file_path.name
                }
            )
            raise ScannedDOCXReadException("An unexpected error occurred while processing the scanned DOCX file.") from e
        finally:
            for img in images:
                try:
                    img.close()
                except Exception:
                    pass

    def _has_images(
            self,
            file_path: Path
    ) -> bool:
        supported_image_formats = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"}
        try:
            with ZipFile(file_path, "r") as docx_zip:
                return any(
                    Path(file_name).suffix.lower() in supported_image_formats
                    for file_name in docx_zip.namelist()
                    if file_name.startswith("word/media/")
                )
        except Exception as e:
            logger.debug(
                "Error checking images in DOCX",
                extra={
                    "file": file_path.name,
                    "error": str(e)
                }
            )
            return False

    def _extract_images_from_docx(
            self,
            file_path: Path
    ) -> List[Image.Image]:
        images: List[Image.Image] = []
        supported_image_formats = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"}
        try:
            with ZipFile(file_path, "r") as docx_zip:
                for file_name in docx_zip.namelist():
                    if not file_name.startswith("word/media/"):
                        continue

                    if Path(file_name).suffix.lower() not in supported_image_formats:
                        continue

                    try:
                        image_data = docx_zip.read(file_name)
                        images.append(Image.open(io.BytesIO(image_data)))
                    except Exception as e:
                        logger.warning(
                            "Failed to extract image from DOCX",
                            extra={
                                "image_name": file_name,
                                "error": str(e)
                            }
                        )

            return images

        except Exception as e:
            logger.error(
                "Failed to extract images from DOCX",
                extra={
                    "file": file_path.name,
                    "error": str(e)
                }
            )
            for img in images:
                try:
                    img.close()
                except Exception:
                    pass
            raise

    def _is_valid_docx(
            self,
            file_path: Path
    ) -> bool:
        docx_magic_numbers = [b"PK\x03\x04"]
        try:
            with open(file_path, "rb") as f:
                header = f.read(4)
                return any(header.startswith(magic) for magic in docx_magic_numbers)
        except Exception:
            return False
