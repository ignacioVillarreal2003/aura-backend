import io
import logging
from pathlib import Path
from zipfile import ZipFile
import pytesseract
from PIL import Image

from app.application.processors.readers.exceptions.reader_exception import (
    ReaderFileNotFoundException,
    ReaderInitializationException,
    ScannedDOCXOCRExtractionException,
    ScannedDOCXReadException,
)
from app.application.processors.readers.instances.base_reader import BaseReader
from app.application.processors.readers.reader_settings import ReaderSettings

logger = logging.getLogger(__name__)

_SUPPORTED_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif", ".webp"})


class ScannedDOCXReader(BaseReader):
    def __init__(
            self,
            reader_settings: ReaderSettings
    ) -> None:
        self._settings = reader_settings

        if not self._settings.tesseract_path:
            raise ReaderInitializationException(
                "The scanned DOCX reader needs Tesseract. Install tesseract-ocr or set READER_TESSERACT_PATH."
            )

        try:
            pytesseract.pytesseract.tesseract_cmd = self._settings.tesseract_path
            logger.info(
                "The scanned DOCX reader was initialized successfully.",
                extra={
                    "tesseract_path": self._settings.tesseract_path,
                    "lang": self._settings.tesseract_lang,
                    "timeout": self._settings.tesseract_timeout
                }
            )
        except Exception as e:
            logger.exception("Failed to initialize the scanned DOCX reader.")
            raise ReaderInitializationException("Failed to initialize the scanned DOCX reader.") from e

    def can_handle(
            self,
            file_path: Path
    ) -> bool:
        if file_path.suffix.lower() != ".docx":
            return False

        return self._has_images(file_path)

    def read(
            self,
            file_path: Path
    ) -> str:
        self._validate_file_exists(file_path)

        logger.info(
            "Reading a scanned DOCX with OCR.",
            extra={
                "file_name": file_path.name,
                "lang": self._settings.tesseract_lang
            }
        )

        images: list[Image.Image] = []
        all_text: list[str] = []

        try:
            images = self._extract_images(file_path)

            logger.info(
                "Images were extracted from the DOCX.",
                extra={
                    "file_name": file_path.name,
                    "images": len(images)
                }
            )

            for i, image in enumerate(images, start=1):
                text = self._run_ocr(image, page_num=i)
                if text:
                    all_text.append(text)

            if not all_text:
                raise ScannedDOCXOCRExtractionException(
                    "OCR processing completed but no extractable text was found "
                    "in the scanned DOCX file."
                )

            logger.info(
                "The scanned DOCX was read successfully.",
                extra={
                    "file_name": file_path.name,
                    "images_with_text": len(all_text)
                }
            )

            return "\n\n".join(all_text)

        except (
                ReaderFileNotFoundException,
                ScannedDOCXOCRExtractionException
        ):
            raise
        except Exception as e:
            logger.exception(
                "An error occurred while reading the scanned DOCX.",
                extra={
                    "file_name": file_path.name
                }
            )
            raise ScannedDOCXReadException(
                "An unexpected error occurred while processing the scanned DOCX file."
            ) from e
        finally:
            _close_images(images)

    def _run_ocr(
            self,
            image: Image.Image,
            page_num: int
    ) -> str:
        try:
            text = pytesseract.image_to_string(
                image,
                lang=self._settings.tesseract_lang,
                timeout=self._settings.tesseract_timeout
            )
            return text.strip() if text else ""
        except pytesseract.TesseractError as e:
            logger.warning(
                "Tesseract reported an error on an image.",
                extra={
                    "image_num": page_num,
                    "exception_type": type(e).__name__
                }
            )
            return ""
        except RuntimeError as e:
            if "timeout" in str(e).lower():
                logger.warning(
                    "OCR timed out on an image.",
                    extra={
                        "image_num": page_num,
                        "timeout": self._settings.tesseract_timeout
                    }
                )
                return ""
            raise
        except Exception as e:
            logger.warning(
                "OCR failed for an image; skipping it.",
                extra={
                    "image_num": page_num,
                    "exception_type": type(e).__name__
                }
            )
            return ""

    def _has_images(
            self,
            file_path: Path
    ) -> bool:
        try:
            with ZipFile(file_path, "r") as zf:
                return any(
                    Path(name).suffix.lower() in _SUPPORTED_IMAGE_EXTENSIONS
                    for name in zf.namelist()
                    if name.startswith("word/media/")
                )
        except Exception as e:
            logger.debug(
                "An error occurred while checking for images in the DOCX.",
                extra={
                    "file_name": file_path.name,
                    "exception_type": type(e).__name__
                }
            )
            return False

    def _extract_images(
            self,
            file_path: Path
    ) -> list[Image.Image]:
        images: list[Image.Image] = []
        try:
            with ZipFile(file_path, "r") as zf:
                for name in zf.namelist():
                    if not name.startswith("word/media/"):
                        continue
                    if Path(name).suffix.lower() not in _SUPPORTED_IMAGE_EXTENSIONS:
                        continue
                    try:
                        images.append(Image.open(io.BytesIO(zf.read(name))))
                    except Exception as e:
                        logger.warning(
                            "Failed to extract an image from the DOCX.",
                            extra={
                                "image_name": name,
                                "exception_type": type(e).__name__
                            }
                        )
            return images
        except Exception as e:
            _close_images(images)
            logger.error(
                "Failed to extract images from the DOCX.",
                extra={
                    "file_name": file_path.name,
                    "exception_type": type(e).__name__
                }
            )
            raise


def _close_images(
        images: list[Image.Image]
) -> None:
    for img in images:
        try:
            img.close()
        except Exception:
            pass
