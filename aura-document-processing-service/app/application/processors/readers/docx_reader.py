from pathlib import Path
from docx import Document
from .interfaces.document_reader_interface import DocumentReaderInterface

class DOCXReader(DocumentReaderInterface):
    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".docx"

    def read(self, file_path: Path) -> str:
        if not file_path.exists():
            raise FileNotFoundError(f"El archivo no existe: {file_path}")

        if not self.can_handle(file_path):
            raise ValueError(f"Formato no soportado por DOCXReader: {file_path.suffix}")

        try:
            doc = Document(file_path)
            text_parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            return "\n".join(text_parts)
        except Exception as e:
            raise IOError(f"Error al leer el archivo DOCX {file_path}: {e}")