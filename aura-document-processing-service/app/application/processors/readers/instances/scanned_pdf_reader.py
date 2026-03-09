import io
import logging
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, TimeoutError, as_completed
from pathlib import Path
from typing import Tuple, Optional
import pytesseract
from pdf2image import convert_from_path
from PIL import Image

from app.application.processors.readers.exceptions.reader_exception import (
    ReaderFileNotFoundException,
    ScannedPDFOCRExtractionException,
    ScannedPDFReadException,
    UnsupportedScannedPDFFormatException
)
from app.application.processors.readers.interfaces.reader_interface import ReaderInterface
from app.application.processors.readers.reader_settings import ReaderSettings

logger = logging.getLogger(__name__)


def _process_single_page_worker(
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
    def __init__(
            self,
            reader_settings: ReaderSettings
    ) -> None:
        self._reader_settings = reader_settings

        if not reader_settings.tesseract_path:
            raise RuntimeError("Tesseract not found. Install tesseract-ocr or set READER_TESSERACT_PATH")

        pytesseract.pytesseract.tesseract_cmd = reader_settings.tesseract_path

        if reader_settings.pdf_max_workers is None:
            self._max_workers = max(1, multiprocessing.cpu_count() - 1)
        else:
            self._max_workers = reader_settings.pdf_max_workers

    def can_handle(
            self,
            file_path: Path
    ) -> bool:
        if file_path.suffix.lower() != ".pdf":
            return False

        if not self._is_valid_pdf(file_path):
            return False

        return True

    def read(
            self,
            file_path: Path
    ) -> str:
        if not file_path.exists():
            raise ReaderFileNotFoundException("The specified PDF file does not exist or cannot be accessed.")

        if not self.can_handle(file_path):
            raise UnsupportedScannedPDFFormatException(
                "The PDF file is not a supported scanned document format for OCR processing."
            )

        logger.info(
            "Reading scanned PDF",
            extra={
                "file": file_path.name,
                "dpi": self._reader_settings.pdf_dpi,
                "lang": self._reader_settings.tesseract_lang,
                "parallel": self._reader_settings.pdf_use_parallel
            }
        )

        pages: list[Image.Image] = []
        try:
            pages = self._convert_pdf_to_images(file_path)

            if not pages:
                raise ScannedPDFOCRExtractionException(
                    "OCR processing completed but no extractable text was found in the scanned PDF file."
                )

            logger.debug(
                "PDF converted to images",
                extra={
                    "pages": len(pages)
                }
            )

            if self._reader_settings.pdf_use_parallel and len(pages) > 1:
                all_text = self._process_pages_parallel(pages)
            else:
                all_text = self._process_pages_sequential(pages)

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
                ScannedPDFOCRExtractionException
        ):
            raise
        except Exception as e:
            logger.exception(
                "Failed to read scanned PDF",
                extra={
                    "file": str(file_path)
                }
            )
            raise ScannedPDFReadException("An unexpected error occurred while processing the scanned PDF file.")
        finally:
            for img in pages:
                try:
                    img.close()
                except Exception:
                    pass

    def _convert_pdf_to_images(
            self,
            file_path: Path
    ) -> list[Image.Image]:
        return convert_from_path(
            str(file_path),
            dpi=self._reader_settings.pdf_dpi,
            poppler_path=self._reader_settings.poppler_path
        )

    def _process_pages_parallel(
            self,
            pages: list[Image.Image]
    ) -> list[str]:
        all_text = [""] * len(pages)
        page_args = []

        for i, page in enumerate(pages):
            try:
                img_byte_arr = io.BytesIO()
                page.save(img_byte_arr, format="PNG")
                page_args.append((
                    img_byte_arr.getvalue(),
                    i,
                    self._reader_settings.tesseract_lang,
                    self._reader_settings.tesseract_timeout,
                ))
            except Exception as e:
                logger.warning(
                    "Failed to serialize page for parallel processing",
                    extra={
                        "page_num": i + 1,
                        "error": str(e)
                    }
                )

        with ProcessPoolExecutor(max_workers=self._max_workers) as executor:
            future_to_page = {
                executor.submit(_process_single_page_worker, args): args[1]
                for args in page_args
            }

            for future in as_completed(future_to_page):
                page_num = future_to_page[future]
                try:
                    result_page_num, text, error = future.result(
                        timeout=self._reader_settings.tesseract_timeout + 5
                    )
                    if error:
                        logger.warning(
                            "OCR worker reported error",
                            extra={
                                "page_num": result_page_num + 1,
                                "error": error
                            }
                        )
                    elif text:
                        all_text[result_page_num] = text
                except TimeoutError:
                    logger.warning(
                        "OCR timeout for page",
                        extra={
                            "page_num": page_num + 1,
                            "timeout": self._reader_settings.tesseract_timeout
                        }
                    )
                except Exception as e:
                    logger.warning(
                        "OCR failed for page",
                        extra={
                            "page_num": page_num + 1,
                            "error": str(e)
                        }
                    )

        return [text for text in all_text if text]

    def _process_pages_sequential(
            self,
            pages: list[Image.Image]
    ) -> list[str]:
        all_text = []

        for i, page in enumerate(pages, start=1):
            try:
                text = pytesseract.image_to_string(
                    page,
                    lang=self._reader_settings.tesseract_lang,
                    timeout=self._reader_settings.tesseract_timeout
                )
                if text.strip():
                    all_text.append(text.strip())
                else:
                    logger.debug(
                        "Page produced no text",
                        extra={
                            "page_num": i
                        }
                    )

            except pytesseract.TesseractError as e:
                logger.warning(
                    "Tesseract error on page",
                    extra={
                        "page_num": i,
                        "error": str(e)
                    }
                )
            except RuntimeError as e:
                if "timeout" in str(e).lower():
                    logger.warning(
                        "OCR timeout on page",
                        extra={
                            "page_num": i,
                            "timeout": self._reader_settings.tesseract_timeout
                        }
                    )
                else:
                    raise
            except Exception as e:
                logger.warning(
                    "OCR failed for page — skipping",
                    extra={
                        "page_num": i,
                        "error": str(e)
                    }
                )

        return all_text

    def _is_valid_pdf(
            self,
            file_path: Path
    ) -> bool:
        pdf_magic_numbers = [b"%PDF"]
        try:
            with open(file_path, "rb") as f:
                header = f.read(5)
                return any(header.startswith(magic) for magic in pdf_magic_numbers)
        except Exception:
            return False
