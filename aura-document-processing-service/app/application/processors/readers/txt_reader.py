from pathlib import Path

from app.application.processors.readers.interfaces.document_reader_interface import DocumentReaderInterface


class TXTReader(DocumentReaderInterface):
    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".txt"

    def read(self, file_path: Path) -> str:
        if not file_path.exists():
            raise FileNotFoundError(f"El archivo no existe: {file_path}")

        if not self.can_handle(file_path):
            raise ValueError(f"Formato no soportado por TXTReader: {file_path.suffix}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            raise IOError(f"Error al leer el archivo TXT {file_path}: {e}")
