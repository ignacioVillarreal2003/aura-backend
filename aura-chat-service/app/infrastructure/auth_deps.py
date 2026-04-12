from typing import Optional

from fastapi import Header
from jose import jwt, JWTError

from app.configuration.environment_variables import settings


async def get_current_user_id(authorization: Optional[str] = Header(None, alias="Authorization")) -> int:
    """
    Extract user_id from the Bearer JWT.
    Falls back to user_id=1 when the token cannot be decoded (dev / mock-auth tokens).
    """
    if not authorization or not authorization.startswith("Bearer "):
        return 1
    token = authorization.removeprefix("Bearer ")
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        raw = payload.get("user_id") or payload.get("sub")
        return int(raw) if raw else 1
    except (JWTError, ValueError, TypeError):
        return 1


async def get_bearer_token(authorization: Optional[str] = Header(None, alias="Authorization")) -> str:
    """
    Return the raw token string to forward to the LLM service.
    Falls back to the dev mock token when no header is present.
    """
    if not authorization:
        return "user_token_123"
    if authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ")
    return authorization
