import logging
from datetime import datetime
from enum import Enum
from typing import Any


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def log_controller(
        logger: logging.Logger,
        *,
        operation: str,
        phase: str,
        **context: Any
) -> None:
    extra: dict[str, Any] = {"operation": operation, "phase": phase}
    for key, value in context.items():
        if value is not None:
            extra[key] = _json_safe_value(value)
    logger.info(
        f"Controller | operation={operation} | phase={phase}",
        extra=extra,
    )
