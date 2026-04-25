from typing import Optional
from fastapi import Header, Request


def optional_idempotency_key(
        request: Request,
        idempotency_key: Optional[str] = Header(
            default=None,
            alias="Idempotency-Key",
        ),
) -> None:
    value = (idempotency_key or "").strip() or None
    request.state.idempotency_key = value
