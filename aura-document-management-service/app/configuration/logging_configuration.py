import logging
import sys
import time
from typing import Any, Dict


STANDARD_ATTRS = {
    'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename', 'module', 'exc_info',
    'exc_text', 'stack_info', 'lineno', 'funcName', 'created', 'msecs', 'relativeCreated', 'thread',
    'threadName', 'processName', 'process', 'message', 'asctime'
}


class ContextualFormatter(logging.Formatter):
    def __init__(self, fmt: str | None = None, datefmt: str | None = None, use_utc: bool = True):
        super().__init__(fmt=fmt, datefmt=datefmt)
        if use_utc:
            self.converter = time.gmtime

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)

        extra_fields: Dict[str, Any] = {}
        for key, value in record.__dict__.items():
            if key not in STANDARD_ATTRS:
                extra_fields[key] = value

        if not extra_fields:
            return base

        extras_rendered = " ".join(
            f"{k}={repr(v)}" for k, v in sorted(extra_fields.items())
        )
        return f"{base} | {extras_rendered}"

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        ct = self.converter(record.created)
        t = time.strftime("%Y-%m-%dT%H:%M:%S", ct)
        return f"{t}.{int(record.msecs):03d}Z"


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
    formatter = ContextualFormatter(fmt=fmt, use_utc=True)

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(formatter)
    root.addHandler(handler)