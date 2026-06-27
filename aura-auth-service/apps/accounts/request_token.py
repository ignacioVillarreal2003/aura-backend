"""Guarda el bearer token de la peticion actual para reenviarlo a otros servicios."""
from __future__ import annotations

import contextvars
from typing import Optional

_request_token: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "aura_request_token", default=None
)


def set_request_token(token: Optional[str]) -> contextvars.Token:
    return _request_token.set(token)


def reset_request_token(token: contextvars.Token) -> None:
    try:
        _request_token.reset(token)
    except (ValueError, LookupError):
        _request_token.set(None)


def get_request_token() -> Optional[str]:
    return _request_token.get()
