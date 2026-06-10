"""Per-request holder for the caller's raw bearer token.

Inter-service calls forward the *user's* token so the downstream service can
validate it (against the shared Redis cache / auth service) and act with the
real user's permissions — instead of self-asserting identity via trust headers.
A ContextVar keeps the token available to the outbound HTTP clients without
threading it through every service/method signature. It is set by the auth
middleware on a successful bearer validation and reset when the request ends.
"""
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
        # Token was set in a different context (e.g. across thread handoff); fall
        # back to clearing it so it cannot leak into the next request.
        _request_token.set(None)


def get_request_token() -> Optional[str]:
    return _request_token.get()
