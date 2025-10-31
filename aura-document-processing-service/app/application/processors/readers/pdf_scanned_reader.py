import os
from pathlib import Path
from pdf2image import convert_from_path
import pytesseract
from .interfaces.document_reader_interface import DocumentReaderInterface

class PDFReaderScanned(DocumentReaderInterface):
    def __init__(self, tesseract_path=None, poppler_path=None):
        self.tesseract_path = tesseract_path or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        self.poppler_path = poppler_path or r"C:\Program Files\poppler-25.07.0\Library\bin"

        if os.path.exists(self.tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_path

    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".pdf"

    def read(self, file_path: Path) -> str:
        if not file_path.exists():
            raise FileNotFoundError(f"El archivo no existe: {file_path}")

        if not self.can_handle(file_path):
            raise ValueError(f"Formato no soportado por PDFReaderScanned: {file_path.suffix}")

        all_text = []
        try:
            pages = convert_from_path(str(file_path), dpi=300, poppler_path=self.poppler_path)

            for i, page in enumerate(pages, start=1):
                text = pytesseract.image_to_string(page, lang="spa")
                if text.strip():
                    all_text.append(text.strip())

            if not all_text:
                raise ValueError("No se extrajo texto mediante OCR.")

            return "\n\n".join(all_text)

        except Exception as e:
            raise IOError(
                f"Error al aplicar OCR al archivo PDF {file_path}. "
                f"¿Está Tesseract/Poppler instalado y configurado? Error: {e}"
            )
