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
    UnsupportedScannedDOCXFormatException
)
from app.application.processors.readers.interfaces.reader_interface import ReaderInterface
from app.application.processors.readers.reader_settings import ReaderSettings

logger = logging.getLogger(__name__)


class ScannedDOCXReader(ReaderInterface):
    _DOCX_MAGIC = b"PK\x03\x04"
    _SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"}

    def __init__(self, reader_settings: ReaderSettings) -> None:
        self._settings = reader_settings

        if not self._settings.tesseract_path:
            raise ReaderInitializationException(
                "ScannedDOCXReader requires a resolved tesseract_path. "
                "Install tesseract-ocr or set READER_TESSERACT_PATH."
            )

        try:
            pytesseract.pytesseract.tesseract_cmd = self._settings.tesseract_path
            logger.info(
                "ScannedDOCXReader initialized successfully",
                extra={
                    "tesseract_path": self._settings.tesseract_path,
                    "lang": self._settings.tesseract_lang,
                    "timeout": self._settings.tesseract_timeout
                }
            )
        except Exception as e:
            logger.exception("Failed to initialize ScannedDOCXReader")
            raise ReaderInitializationException(
                f"ScannedDOCXReader initialization failed: {e}"
            ) from e

    def can_handle(self, file_path: Path) -> bool:
        if file_path.suffix.lower() != ".docx":
            return False

        if not self._is_valid_docx(file_path):
            return False

        return self._has_images(file_path)

    def read(self, file_path: Path) -> str:
        if not file_path.exists():
            raise ReaderFileNotFoundException(
                "The specified DOCX file does not exist or cannot be accessed."
            )

        if not self.can_handle(file_path):
            raise UnsupportedScannedDOCXFormatException(
                "The DOCX file is not a supported scanned document_controllers format for OCR processing."
            )

        logger.info(
            "Reading scanned DOCX",
            extra={"file": file_path.name, "lang": self._settings.tesseract_lang}
        )

        images: list[Image.Image] = []
        all_text: list[str] = []

        try:
            images = self._extract_images(file_path)

            logger.info(
                "Extracted images from DOCX",
                extra={"file": file_path.name, "images": len(images)}
            )

            for i, image in enumerate(images, start=1):
                text = self._run_ocr(image, page_num=i)
                if text:
                    all_text.append(text)

            if not all_text:
                raise ScannedDOCXOCRExtractionException(
                    "OCR processing completed but no extractable text was found in the scanned DOCX file."
                )

            logger.info(
                "Scanned DOCX read successfully",
                extra={"file": file_path.name, "images_with_text": len(all_text)}
            )

            return "\n\n".join(all_text)

        except (
                ReaderFileNotFoundException,
                UnsupportedScannedDOCXFormatException,
                ScannedDOCXOCRExtractionException,
        ):
            raise
        except Exception as e:
            logger.exception("Error reading scanned DOCX", extra={"file": file_path.name})
            raise ScannedDOCXReadException(
                "An unexpected error occurred while processing the scanned DOCX file."
            ) from e
        finally:
            _close_images(images)

    def _run_ocr(self, image: Image.Image, page_num: int) -> str:
        try:
            text = pytesseract.image_to_string(
                image,
                lang=self._settings.tesseract_lang,
                timeout=self._settings.tesseract_timeout,
            )
            return text.strip() if text else ""
        except pytesseract.TesseractError as e:
            logger.warning("Tesseract error on image", extra={"image_num": page_num, "error": str(e)})
            return ""
        except RuntimeError as e:
            if "timeout" in str(e).lower():
                logger.warning(
                    "OCR timeout on image",
                    extra={"image_num": page_num, "timeout": self._settings.tesseract_timeout}
                )
                return ""
            raise
        except Exception as e:
            logger.warning("OCR failed for image — skipping", extra={"image_num": page_num, "error": str(e)})
            return ""

    def _has_images(self, file_path: Path) -> bool:
        try:
            with ZipFile(file_path, "r") as zf:
                return any(
                    Path(name).suffix.lower() in self._SUPPORTED_IMAGE_EXTENSIONS
                    for name in zf.namelist()
                    if name.startswith("word/media/")
                )
        except Exception as e:
            logger.debug("Error checking images in DOCX", extra={"file": file_path.name, "error": str(e)})
            return False

    def _extract_images(self, file_path: Path) -> list[Image.Image]:
        images: list[Image.Image] = []
        try:
            with ZipFile(file_path, "r") as zf:
                for name in zf.namelist():
                    if not name.startswith("word/media/"):
                        continue
                    if Path(name).suffix.lower() not in self._SUPPORTED_IMAGE_EXTENSIONS:
                        continue
                    try:
                        images.append(Image.open(io.BytesIO(zf.read(name))))
                    except Exception as e:
                        logger.warning(
                            "Failed to extract image from DOCX",
                            extra={"image_name": name, "error": str(e)}
                        )
            return images
        except Exception as e:
            _close_images(images)
            logger.error("Failed to extract images from DOCX", extra={"file": file_path.name, "error": str(e)})
            raise

    def _is_valid_docx(self, file_path: Path) -> bool:
        try:
            with open(file_path, "rb") as f:
                return f.read(4).startswith(self._DOCX_MAGIC)
        except Exception:
            return False


def _close_images(images: list[Image.Image]) -> None:
    for img in images:
        try:
            img.close()
        except Exception:
            pass
