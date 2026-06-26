"""Unit tests for configure_logging: the root JSON handler is installed and
uvicorn's own loggers are re-pointed at it (handlers cleared but propagation
re-enabled) so their lifecycle lines are not silently dropped."""
import logging

import pytest

from app.configuration.logging_configuration import JSONFormatter, configure_logging


@pytest.fixture
def restore_logging():
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    saved_uvicorn = {
        name: (logging.getLogger(name).handlers[:], logging.getLogger(name).propagate)
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access")
    }
    try:
        yield
    finally:
        root.handlers = saved_handlers
        root.setLevel(saved_level)
        for name, (handlers, propagate) in saved_uvicorn.items():
            lg = logging.getLogger(name)
            lg.handlers = handlers
            lg.propagate = propagate


def test_root_has_single_json_handler(restore_logging):
    configure_logging(level=logging.INFO)
    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, JSONFormatter)
    assert root.level == logging.INFO


def test_uvicorn_loggers_propagate_with_no_handlers(restore_logging):
    # Simulate uvicorn's default config (own handler, propagation disabled).
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers = [logging.NullHandler()]
        lg.propagate = False

    configure_logging(level=logging.INFO)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        assert lg.handlers == []
        assert lg.propagate is True


def test_uvicorn_records_reach_root_handler(restore_logging):
    configure_logging(level=logging.INFO)
    root = logging.getLogger()
    formatted: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            formatted.append(self.format(record))

    capture = _Capture()
    capture.setFormatter(JSONFormatter(use_utc=True))
    root.addHandler(capture)

    logging.getLogger("uvicorn").info("Uvicorn running on http://0.0.0.0:8000")

    assert any("Uvicorn running" in line for line in formatted)
