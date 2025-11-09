from pathlib import Path
from typing import List

from app.application.processors.readers.docx_reader import DOCXReader
from app.application.processors.readers.interfaces.document_reader_interface import DocumentReaderInterface
from app.application.processors.readers.pdf_reader_digital import PDFReaderDigital
from app.application.processors.readers.pdf_scanned_reader import PDFReaderScanned
from app.application.processors.readers.txt_reader import TXTReader


class ReaderFactory:
    def __init__(self):
        self._readers: List[DocumentReaderInterface] = [
            PDFReaderDigital(),
            PDFReaderScanned(),
            DOCXReader(),
            TXTReader()
        ]

    def get_reader(self, file_path: Path) -> DocumentReaderInterface:
        for reader in self._readers:
            try:
                if reader.can_handle(file_path):
                    return reader
            except Exception:
                continue
        raise ValueError(f"No se encontró lector compatible para el archivo: {file_path}")
