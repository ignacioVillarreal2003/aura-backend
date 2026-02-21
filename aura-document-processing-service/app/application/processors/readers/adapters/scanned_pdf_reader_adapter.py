import logging
import os
import platform
import shutil
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Tuple
import multiprocessing

from pdf2image import convert_from_path
import pytesseract

from app.application.processors.readers.exceptions.reader_exception import (
    ReaderFileNotFoundException,
    UnsupportedScannedPDFFormatException,
    ScannedPDFOCRExtractionException,
    ScannedPDFReadException
)
from app.application.processors.readers.interfaces.reader_adapter_interface import DocumentReaderInterface

logger = logging.getLogger(__name__)


class ScannedPDFReaderAdapter(DocumentReaderInterface):
    def __init__(
            self,
            use_parallel: bool = True,
            max_workers: int = None,
            dpi: int = 300,
            lang: str = "spa"
    ):
        self.tesseract_path = None
        self.poppler_path = None
        self.use_parallel = use_parallel
        self.dpi = dpi
        self.lang = lang

        if max_workers is None:
            cpu_count = multiprocessing.cpu_count()
            self.max_workers = max(1, cpu_count - 1)
        else:
            self.max_workers = max_workers

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

    def _process_pages_parallel(
            self,
            pages: List
    ) -> List[str]:
        all_text = [""] * len(pages)

        page_args = [(page, i, self.lang) for i, page in enumerate(pages)]

        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_page = {
                executor.submit(self._process_single_page, args): args[1]
                for args in page_args
            }

            for future in as_completed(future_to_page):
                page_num = future_to_page[future]
                try:
                    page_num, text = future.result()
                    if text:
                        all_text[page_num] = text
                except Exception as e:
                    logger.warning(f"OCR failed for page {page_num} — skipping [reason={e}]")

        return [text for text in all_text if text]

    @staticmethod
    def _process_single_page(args: Tuple[object, int, str]) -> Tuple[int, str]:
        page_image, page_num, lang = args
        text = pytesseract.image_to_string(page_image, lang=lang)
        return (page_num, text.strip() if text else "")

    def _process_pages_sequential(
            self,
            pages: List
    ) -> List[str]:
        all_text = []

        for i, page in enumerate(pages, start=1):
            try:
                text = pytesseract.image_to_string(page, lang=self.lang)
                if text.strip():
                    all_text.append(text.strip())
            except Exception as e:
                logger.warning(f"OCR failed for page {i} — skipping [reason={e}]")

        return all_text

    def read(
            self,
            file_path: Path
    ) -> str:
        if not file_path.exists():
            raise ReaderFileNotFoundException(str(file_path))

        if not self.can_handle(file_path):
            raise UnsupportedScannedPDFFormatException(file_path.suffix)

        logger.info(
            f"Reading scanned PDF [file={file_path.name}, dpi={self.dpi}, lang={self.lang}, parallel={self.use_parallel}]"
        )

        try:
            pages = convert_from_path(
                str(file_path),
                dpi=self.dpi,
                poppler_path=self.poppler_path
            )

            if not pages:
                raise ScannedPDFOCRExtractionException()

            logger.info(f"PDF converted to images [file={file_path.name}, pages={len(pages)}]")

            if self.use_parallel and len(pages) > 1:
                all_text = self._process_pages_parallel(pages)
            else:
                all_text = self._process_pages_sequential(pages)

            if not all_text:
                raise ScannedPDFOCRExtractionException()

            logger.info(
                f"Scanned PDF read successfully [file={file_path.name}, pages_with_text={len(all_text)}/{len(pages)}]"
            )
            return "\n\n".join(all_text)

        except (ReaderFileNotFoundException, UnsupportedScannedPDFFormatException, ScannedPDFOCRExtractionException):
            raise
        except Exception as e:
            raise ScannedPDFReadException(str(file_path), e)
