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
    ReaderFileNotFoundError,
    UnsupportedScannedPDFFormatError,
    ScannedPDFOCRExtractionError,
    ScannedPDFReadError
)
from app.application.processors.readers.interfaces.reader_adapter_interface import DocumentReaderInterface


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
                try:
                    page_num, text = future.result()
                    if text:
                        all_text[page_num] = text
                except Exception as e:
                    page_num = future_to_page[future]
                    all_text[page_num] = f"[Error en página {page_num}: {str(e)}]"

        return [text for text in all_text if text]

    @staticmethod
    def _process_single_page(args: Tuple[object, int, str]) -> Tuple[int, str]:
        page_image, page_num, lang = args
        try:
            text = pytesseract.image_to_string(page_image, lang=lang)
            return (page_num, text.strip() if text else "")
        except Exception as e:
            return (page_num, f"[Error procesando página {page_num}: {str(e)}]")

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
                all_text.append(f"[Error en página {i}: {str(e)}]")

        return all_text

    def read(
            self,
            file_path: Path
    ) -> str:
        if not file_path.exists():
            raise ReaderFileNotFoundError(str(file_path))

        if not self.can_handle(file_path):
            raise UnsupportedScannedPDFFormatError(file_path.suffix)

        try:
            pages = convert_from_path(
                str(file_path),
                dpi=self.dpi,
                poppler_path=self.poppler_path
            )

            if not pages:
                raise ScannedPDFOCRExtractionError()

            if self.use_parallel and len(pages) > 1:
                all_text = self._process_pages_parallel(pages)
            else:
                all_text = self._process_pages_sequential(pages)

            if not all_text:
                raise ScannedPDFOCRExtractionError()

            return "\n\n".join(all_text)

        except (ReaderFileNotFoundError, UnsupportedScannedPDFFormatError, ScannedPDFOCRExtractionError):
            raise
        except Exception as e:
            raise ScannedPDFReadError(str(file_path), e)
