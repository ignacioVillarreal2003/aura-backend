from contextvars import ContextVar
from typing import Optional
from fastapi import Request

_request_token: ContextVar[Optional[str]] = ContextVar("_request_token", default=None)

REQUEST_TOKEN_STATE_ATTR = "request_token"


def set_request_token(token: Optional[str]) -> None:
    _request_token.set(token)


def get_request_token() -> Optional[str]:
    return _request_token.get()


async def bind_request_token(request: Request) -> None:
    set_request_token(getattr(request.state, REQUEST_TOKEN_STATE_ATTR, None))
