from contextvars import ContextVar
from typing import Optional

_request_token: ContextVar[Optional[str]] = ContextVar("_request_token", default=None)


def set_request_token(token: Optional[str]) -> None:
    _request_token.set(token)


def get_request_token() -> Optional[str]:
    return _request_token.get()
