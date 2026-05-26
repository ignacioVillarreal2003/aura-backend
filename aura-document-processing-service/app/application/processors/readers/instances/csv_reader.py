import csv
import io
import logging
from pathlib import Path
from typing import Optional

from app.application.processors.readers.exceptions.reader_exception import (
    CSVHasNoContentException,
    CSVReadException,
    ReaderFileNotFoundException,
)
from app.application.processors.readers.instances.base_reader import BaseReader
from app.application.processors.readers.reader_settings import ReaderSettings

logger = logging.getLogger(__name__)

_DECODE_ENCODINGS: tuple[str, ...] = ("utf-8-sig", "utf-8", "latin-1", "cp1252")
_MAX_ROWS = 10_000


class CSVReader(BaseReader):
    def __init__(
            self,
            reader_settings: Optional[ReaderSettings] = None,
    ) -> None:
        self._settings = reader_settings or ReaderSettings()
        logger.info("The CSV reader was initialized successfully.")

    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".csv"

    def read(self, file_path: Path) -> str:
        self._validate_file_exists(file_path)

        logger.info(
            "Reading a CSV file.",
            extra={"file_name": file_path.name},
        )

        try:
            raw = file_path.read_bytes()
            text = self._decode(raw)
            rows = self._parse(text)

            if not rows:
                raise CSVHasNoContentException("The CSV file contains no readable rows.")

            result = self._to_text(rows)

            logger.info(
                "The CSV file was read successfully.",
                extra={
                    "file_name": file_path.name,
                    "total_rows": len(rows),
                    "columns": len(rows[0]) if rows else 0,
                    "truncated": len(rows) > _MAX_ROWS,
                },
            )
            return result

        except (ReaderFileNotFoundException, CSVHasNoContentException):
            raise
        except CSVReadException:
            raise
        except Exception as e:
            logger.exception(
                "An error occurred while reading the CSV file.",
                extra={"file_name": file_path.name},
            )
            raise CSVReadException(
                "An unexpected error occurred while reading the CSV file."
            ) from e

    @staticmethod
    def _decode(raw: bytes) -> str:
        for encoding in _DECODE_ENCODINGS:
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise CSVReadException(
            "Could not decode the CSV file with any of the supported encodings "
            f"({', '.join(_DECODE_ENCODINGS)})."
        )

    @staticmethod
    def _parse(text: str) -> list[list[str]]:
        try:
            sample = text[:4096]
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            except csv.Error:
                dialect = csv.excel
            reader = csv.reader(io.StringIO(text), dialect)
            return [
                [cell.strip() for cell in row]
                for row in reader
                if any(cell.strip() for cell in row)
            ]
        except csv.Error as e:
            raise CSVReadException("Failed to parse the CSV content.") from e

    @staticmethod
    def _to_text(rows: list[list[str]]) -> str:
        limited = rows[:_MAX_ROWS]
        lines = [" | ".join(row) for row in limited]
        if len(rows) > _MAX_ROWS:
            lines.append(f"[truncated — showing {_MAX_ROWS} of {len(rows)} rows]")
        return "\n".join(lines)
