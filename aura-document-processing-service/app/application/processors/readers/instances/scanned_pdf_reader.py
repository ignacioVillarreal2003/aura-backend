import io
import logging
import multiprocessing
import threading
from concurrent.futures import ProcessPoolExecutor, TimeoutError, as_completed
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path
from typing import Optional
import pypdf
import pytesseract
from pdf2image import convert_from_path
from PIL import Image

from app.application.processors.readers.exceptions.reader_exception import (
    ReaderFileNotFoundException,
    ReaderInitializationException,
    ScannedPDFOCRExtractionException,
    ScannedPDFReadException,
)
from app.application.processors.readers.instances.base_reader import BaseReader
from app.application.processors.readers.reader_settings import ReaderSettings

logger = logging.getLogger(__name__)

def _ocr_page_worker(
        args: tuple[bytes, int, str, int, str | None],
) -> tuple[int, str, Optional[str]]:
    import io
    import pytesseract
    from PIL import Image

    image_bytes, page_num, lang, timeout, tesseract_path = args
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
    try:
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image, lang=lang, timeout=timeout)
        image.close()
        return (page_num, text.strip() if text else "", None)
    except Exception as e:
        return (page_num, "", type(e).__name__)


class ScannedPDFReader(BaseReader):
    def __init__(
            self,
            reader_settings: ReaderSettings
    ) -> None:
        self._settings = reader_settings

        if not self._settings.tesseract_path:
            raise ReaderInitializationException(
                "The scanned PDF reader needs Tesseract. Install tesseract-ocr or set READER_TESSERACT_PATH."
            )

        try:
            pytesseract.pytesseract.tesseract_cmd = self._settings.tesseract_path

            self._max_workers: int = (
                self._settings.pdf_max_workers
                if self._settings.pdf_max_workers is not None
                else max(1, multiprocessing.cpu_count() - 1)
            )

            self._pool: Optional[ProcessPoolExecutor] = None
            self._pool_lock = threading.Lock()

            logger.info(
                "The scanned PDF reader was initialized successfully.",
                extra={
                    "tesseract_path": self._settings.tesseract_path,
                    "lang": self._settings.tesseract_lang,
                    "dpi": self._settings.pdf_dpi,
                    "parallel": self._settings.pdf_use_parallel,
                    "max_workers": self._max_workers
                }
            )
        except Exception as e:
            logger.exception("Failed to initialize the scanned PDF reader.")
            raise ReaderInitializationException("Failed to initialize the scanned PDF reader.") from e

    def can_handle(
            self,
            file_path: Path
    ) -> bool:
        if file_path.suffix.lower() != ".pdf":
            return False
        try:
            with open(file_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                if len(reader.pages) == 0:
                    return False
                pages_to_probe = min(len(reader.pages), 3)
                for i in range(pages_to_probe):
                    text = reader.pages[i].extract_text()
                    if text and text.strip():
                        return False
            return True
        except Exception:
            return True

    def read(
            self,
            file_path: Path
    ) -> str:
        self._validate_file_exists(file_path)

        logger.info(
            "Reading a scanned PDF with OCR.",
            extra={
                "file_name": file_path.name,
                "dpi": self._settings.pdf_dpi,
                "lang": self._settings.tesseract_lang,
                "parallel": self._settings.pdf_use_parallel
            }
        )

        pages: list[Image.Image] = []
        try:
            pages = self._convert_to_images(file_path)

            if not pages:
                raise ScannedPDFOCRExtractionException("The PDF could not be converted to images; no pages were found.")

            logger.debug(
                "The PDF was converted to images.",
                extra={
                    "pages": len(pages)
                }
            )

            all_text = (
                self._process_parallel(pages)
                if self._settings.pdf_use_parallel and len(pages) > 1
                else self._process_sequential(pages)
            )

            if not all_text:
                raise ScannedPDFOCRExtractionException(
                    "OCR processing completed but no extractable text was found "
                    "in the scanned PDF file."
                )

            logger.info(
                "The scanned PDF was read successfully.",
                extra={
                    "file_name": file_path.name,
                    "total_pages": len(pages),
                    "pages_with_text": len(all_text)
                }
            )

            return "\n\n".join(all_text)

        except (
                ReaderFileNotFoundException,
                ScannedPDFOCRExtractionException,
        ):
            raise
        except Exception as e:
            logger.exception(
                "Failed to read the scanned PDF.",
                extra={
                    "file_name": file_path.name
                }
            )
            raise ScannedPDFReadException("An unexpected error occurred while processing the scanned PDF file.") from e
        finally:
            _close_images(pages)

    def _convert_to_images(
            self,
            file_path: Path
    ) -> list[Image.Image]:
        last_page = self._resolve_last_page(file_path)
        return convert_from_path(
            str(file_path),
            dpi=self._settings.pdf_dpi,
            poppler_path=self._settings.poppler_path,
            first_page=1,
            last_page=last_page,
        )

    def _resolve_last_page(
            self,
            file_path: Path
    ) -> int:
        cap = self._settings.pdf_max_ocr_pages
        total = self._page_count(file_path)
        if total is not None and total > cap:
            logger.warning(
                "The scanned PDF exceeds the OCR page cap; only the first pages will be processed.",
                extra={
                    "file_name": file_path.name,
                    "total_pages": total,
                    "page_cap": cap,
                }
            )
        return cap if total is None else min(total, cap)

    @staticmethod
    def _page_count(
            file_path: Path
    ) -> Optional[int]:
        try:
            with open(file_path, "rb") as f:
                return len(pypdf.PdfReader(f).pages)
        except Exception:
            return None

    def _process_sequential(
            self,
            pages: list[Image.Image]
    ) -> list[str]:
        all_text: list[str] = []

        for i, page in enumerate(pages, start=1):
            try:
                text = pytesseract.image_to_string(
                    page,
                    lang=self._settings.tesseract_lang,
                    timeout=self._settings.tesseract_timeout
                )
                if text and text.strip():
                    all_text.append(text.strip())
                else:
                    logger.debug(
                        "A page produced no text.",
                        extra={
                            "page_num": i
                        }
                    )

            except pytesseract.TesseractError as e:
                logger.warning(
                    "Tesseract reported an error on a page.",
                    extra={
                        "page_num": i,
                        "exception_type": type(e).__name__
                    }
                )
            except RuntimeError as e:
                if "timeout" in str(e).lower():
                    logger.warning(
                        "OCR timed out on a page.",
                        extra={
                            "page_num": i,
                            "timeout": self._settings.tesseract_timeout
                        }
                    )
                else:
                    raise
            except Exception as e:
                logger.warning(
                    "OCR failed for a page; skipping that page.",
                    extra={
                        "page_num": i,
                        "exception_type": type(e).__name__
                    }
                )

        return all_text

    def _process_parallel(
            self,
            pages: list[Image.Image]
    ) -> list[str]:
        try:
            return self._run_pool_ocr(pages)
        except BrokenProcessPool:
            logger.warning(
                "The OCR process pool broke; resetting it and falling back to "
                "sequential OCR for this document.",
            )
            self._reset_pool()
            return self._process_sequential(pages)

    def _run_pool_ocr(
            self,
            pages: list[Image.Image]
    ) -> list[str]:
        all_text: list[Optional[str]] = [None] * len(pages)
        max_in_flight = max(1, self._max_workers * 2)
        next_page_to_submit = 0

        executor = self._get_pool()
        future_to_page: dict = {}

        while next_page_to_submit < len(pages) or future_to_page:
            while (
                    next_page_to_submit < len(pages)
                    and len(future_to_page) < max_in_flight
            ):
                page = pages[next_page_to_submit]
                page_index = next_page_to_submit
                next_page_to_submit += 1
                try:
                    buf = io.BytesIO()
                    page.save(buf, format="PNG")
                    payload: tuple[bytes, int, str, int, str | None] = (
                        buf.getvalue(),
                        page_index,
                        self._settings.tesseract_lang,
                        self._settings.tesseract_timeout,
                        self._settings.tesseract_path,
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to serialize a page for parallel OCR.",
                        extra={
                            "page_num": page_index + 1,
                            "exception_type": type(e).__name__
                        }
                    )
                    continue

                future = executor.submit(_ocr_page_worker, payload)
                future_to_page[future] = page_index

            if not future_to_page:
                continue

            future = next(as_completed(future_to_page))
            page_num = future_to_page.pop(future)
            try:
                result_page_num, text, error = future.result(
                    timeout=self._settings.tesseract_timeout + 5
                )
                if error:
                    logger.warning(
                        "The OCR worker reported a problem for a page.",
                        extra={
                            "page_num": result_page_num + 1
                        }
                    )
                elif text:
                    all_text[result_page_num] = text
            except TimeoutError:
                logger.warning(
                    "OCR timed out for a page.",
                    extra={
                        "page_num": page_num + 1,
                        "timeout": self._settings.tesseract_timeout
                    }
                )
            except BrokenProcessPool:
                raise
            except Exception as e:
                logger.warning(
                    "OCR failed for a page.",
                    extra={
                        "page_num": page_num + 1,
                        "exception_type": type(e).__name__
                    }
                )

        return [t for t in all_text if t]

    def _get_pool(
            self
    ) -> ProcessPoolExecutor:
        pool = self._pool
        if pool is not None:
            return pool
        with self._pool_lock:
            if self._pool is None:
                self._pool = ProcessPoolExecutor(max_workers=self._max_workers)
                logger.info(
                    "Initialized the persistent OCR process pool.",
                    extra={"max_workers": self._max_workers},
                )
            return self._pool

    def _reset_pool(
            self
    ) -> None:
        with self._pool_lock:
            pool = self._pool
            self._pool = None
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)


def _close_images(
        images: list[Image.Image]
) -> None:
    for img in images:
        try:
            img.close()
        except Exception:
            pass
