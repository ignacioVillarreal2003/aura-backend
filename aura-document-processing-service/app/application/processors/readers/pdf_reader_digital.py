from pathlib import Path
import pypdf

from app.application.processors.readers.interfaces.document_reader_interface import DocumentReaderInterface


class PDFReaderDigital(DocumentReaderInterface):
    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".pdf"

    def read(self, file_path: Path) -> str:
        if not file_path.exists():
            raise FileNotFoundError(f"El archivo no existe: {file_path}")

        if not self.can_handle(file_path):
            raise ValueError(f"Formato no soportado por PDFReaderDigital: {file_path.suffix}")

        text_parts = []
        try:
            with open(file_path, "rb") as file:
                pdf_reader = pypdf.PdfReader(file)
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text.strip())

            if not text_parts:
                raise ValueError("El PDF parece no tener texto extraíble (posiblemente escaneado).")

            return "\n\n".join(text_parts)

        except Exception as e:
            raise IOError(f"Error al leer el archivo PDF {file_path}: {e}")