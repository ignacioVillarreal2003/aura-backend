import logging
import sys
import time
import json
from datetime import datetime
from enum import Enum
from typing import Any

STANDARD_ATTRS = {
    'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename', 'module', 'exc_info',
    'exc_text', 'stack_info', 'lineno', 'funcName', 'created', 'msecs', 'relativeCreated', 'thread',
    'threadName', 'processName', 'process', 'message', 'asctime'
}


class JSONFormatter(logging.Formatter):
    def __init__(
            self,
            fmt: str | None = None,
            datefmt: str | None = None,
            use_utc: bool = True
    ):
        super().__init__(
            fmt=fmt,
            datefmt=datefmt
        )
        if use_utc:
            self.converter = time.gmtime

    def format(
            self,
            record: logging.LogRecord
    ) -> str:
        log_record = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "location": f"{record.filename}:{record.lineno}"
        }

        context: dict[str, Any] = {}
        for key, value in record.__dict__.items():
            if key not in STANDARD_ATTRS:
                context[key] = self._json_safe(value)

        if context:
            log_record["context"] = context

        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            log_record["exception"] = record.exc_text

        return json.dumps(log_record)

    @staticmethod
    def _json_safe(
            value: Any
    ) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        try:
            json.dumps(value)
            return value
        except (TypeError, ValueError):
            return str(value)

    def formatTime(
            self,
            record: logging.LogRecord,
            datefmt: str | None = None
    ) -> str:
        ct = self.converter(record.created)
        t = time.strftime("%Y-%m-%dT%H:%M:%S", ct)
        return f"{t}.{int(record.msecs):03d}Z"


def configure_logging(
        level: int = logging.INFO
) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    formatter = JSONFormatter(use_utc=True)

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(formatter)
    root.addHandler(handler)

    logging.getLogger("uvicorn").handlers = []
    logging.getLogger("uvicorn.access").handlers = []
