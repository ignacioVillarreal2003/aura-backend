import io
import logging
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, TimeoutError, as_completed
from pathlib import Path
from typing import Optional, Tuple
import pytesseract
from pdf2image import convert_from_path
from PIL import Image

from app.application.processors.readers.exceptions.reader_exception import (
    ReaderFileNotFoundException,
    ReaderInitializationException,
    ScannedPDFOCRExtractionException,
    ScannedPDFReadException,
    UnsupportedScannedPDFFormatException
)
from app.application.processors.readers.interfaces.reader_interface import ReaderInterface
from app.application.processors.readers.reader_settings import ReaderSettings

logger = logging.getLogger(__name__)


def _ocr_page_worker(
        args: Tuple[bytes, int, str, int],
) -> Tuple[int, str, Optional[str]]:
    import io
    import pytesseract
    from PIL import Image

    image_bytes, page_num, lang, timeout = args
    try:
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image, lang=lang, timeout=timeout)
        image.close()
        return (page_num, text.strip() if text else "", None)
    except Exception as e:
        return (page_num, "", str(e))


class ScannedPDFReader(ReaderInterface):
    _PDF_MAGIC = b"%PDF"

    def __init__(self, reader_settings: ReaderSettings) -> None:
        self._settings = reader_settings

        if not self._settings.tesseract_path:
            raise ReaderInitializationException(
                "ScannedPDFReader requires a resolved tesseract_path. "
                "Install tesseract-ocr or set READER_TESSERACT_PATH."
            )

        try:
            pytesseract.pytesseract.tesseract_cmd = self._settings.tesseract_path

            self._max_workers: int = (
                self._settings.pdf_max_workers
                if self._settings.pdf_max_workers is not None
                else max(1, multiprocessing.cpu_count() - 1)
            )

            logger.info(
                "ScannedPDFReader initialized successfully",
                extra={
                    "tesseract_path": self._settings.tesseract_path,
                    "lang": self._settings.tesseract_lang,
                    "dpi": self._settings.pdf_dpi,
                    "parallel": self._settings.pdf_use_parallel,
                    "max_workers": self._max_workers
                }
            )
        except Exception as e:
            logger.exception("Failed to initialize ScannedPDFReader")
            raise ReaderInitializationException(
                f"ScannedPDFReader initialization failed: {e}"
            ) from e

    def can_handle(self, file_path: Path) -> bool:
        if file_path.suffix.lower() != ".pdf":
            return False
        return self._is_valid_pdf(file_path)

    def read(self, file_path: Path) -> str:
        if not file_path.exists():
            raise ReaderFileNotFoundException(
                "The specified PDF file does not exist or cannot be accessed."
            )

        if not self.can_handle(file_path):
            raise UnsupportedScannedPDFFormatException(
                "The PDF file is not a supported scanned document_controllers format for OCR processing."
            )

        logger.info(
            "Reading scanned PDF",
            extra={
                "file": file_path.name,
                "dpi": self._settings.pdf_dpi,
                "lang": self._settings.tesseract_lang,
                "parallel": self._settings.pdf_use_parallel
            }
        )

        pages: list[Image.Image] = []
        try:
            pages = self._convert_to_images(file_path)

            if not pages:
                raise ScannedPDFOCRExtractionException(
                    "PDF could not be converted to images — no pages found."
                )

            logger.debug("PDF converted to images", extra={"pages": len(pages)})

            all_text = (
                self._process_parallel(pages)
                if self._settings.pdf_use_parallel and len(pages) > 1
                else self._process_sequential(pages)
            )

            if not all_text:
                raise ScannedPDFOCRExtractionException(
                    "OCR processing completed but no extractable text was found in the scanned PDF file."
                )

            logger.info(
                "Scanned PDF read successfully",
                extra={
                    "file": file_path.name,
                    "total_pages": len(pages),
                    "pages_with_text": len(all_text)
                }
            )

            return "\n\n".join(all_text)

        except (
                ReaderFileNotFoundException,
                UnsupportedScannedPDFFormatException,
                ScannedPDFOCRExtractionException,
        ):
            raise
        except Exception as e:
            logger.exception("Failed to read scanned PDF", extra={"file": str(file_path)})
            raise ScannedPDFReadException(
                "An unexpected error occurred while processing the scanned PDF file."
            ) from e
        finally:
            _close_images(pages)

    def _convert_to_images(self, file_path: Path) -> list[Image.Image]:
        return convert_from_path(
            str(file_path),
            dpi=self._settings.pdf_dpi,
            poppler_path=self._settings.poppler_path
        )

    def _process_sequential(self, pages: list[Image.Image]) -> list[str]:
        all_text: list[str] = []

        for i, page in enumerate(pages, start=1):
            try:
                text = pytesseract.image_to_string(
                    page,
                    lang=self._settings.tesseract_lang,
                    timeout=self._settings.tesseract_timeout,
                )
                if text and text.strip():
                    all_text.append(text.strip())
                else:
                    logger.debug("Page produced no text", extra={"page_num": i})

            except pytesseract.TesseractError as e:
                logger.warning("Tesseract error on page", extra={"page_num": i, "error": str(e)})
            except RuntimeError as e:
                if "timeout" in str(e).lower():
                    logger.warning(
                        "OCR timeout on page",
                        extra={"page_num": i, "timeout": self._settings.tesseract_timeout}
                    )
                else:
                    raise
            except Exception as e:
                logger.warning("OCR failed for page — skipping", extra={"page_num": i, "error": str(e)})

        return all_text

    def _process_parallel(self, pages: list[Image.Image]) -> list[str]:
        all_text: list[Optional[str]] = [None] * len(pages)
        page_args: list[Tuple[bytes, int, str, int]] = []

        for i, page in enumerate(pages):
            try:
                buf = io.BytesIO()
                page.save(buf, format="PNG")
                page_args.append((
                    buf.getvalue(),
                    i,
                    self._settings.tesseract_lang,
                    self._settings.tesseract_timeout,
                ))
            except Exception as e:
                logger.warning(
                    "Failed to serialize page for parallel processing",
                    extra={"page_num": i + 1, "error": str(e)}
                )

        with ProcessPoolExecutor(max_workers=self._max_workers) as executor:
            future_to_page = {
                executor.submit(_ocr_page_worker, args): args[1]
                for args in page_args
            }

            for future in as_completed(future_to_page):
                page_num = future_to_page[future]
                try:
                    result_page_num, text, error = future.result(
                        timeout=self._settings.tesseract_timeout + 5
                    )
                    if error:
                        logger.warning(
                            "OCR worker error",
                            extra={"page_num": result_page_num + 1, "error": error},
                        )
                    elif text:
                        all_text[result_page_num] = text
                except TimeoutError:
                    logger.warning(
                        "OCR timeout for page",
                        extra={"page_num": page_num + 1, "timeout": self._settings.tesseract_timeout},
                    )
                except Exception as e:
                    logger.warning("OCR failed for page", extra={"page_num": page_num + 1, "error": str(e)})

        return [t for t in all_text if t]

    def _is_valid_pdf(self, file_path: Path) -> bool:
        try:
            with open(file_path, "rb") as f:
                return f.read(5).startswith(self._PDF_MAGIC)
        except Exception:
            return False


def _close_images(images: list[Image.Image]) -> None:
    for img in images:
        try:
            img.close()
        except Exception:
            pass
