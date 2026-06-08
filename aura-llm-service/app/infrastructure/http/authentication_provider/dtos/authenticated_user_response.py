import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from app.domain.field_limits import (
    MAX_ID,
    MAX_EMAIL_CHARS,
    MAX_PERMISSIONS,
    MAX_ROLES,
    MAX_ROLE_CHARS,
    MAX_PERMISSION_CHARS,
)

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthenticatedUserResponse(BaseModel):
    id: int = Field(..., ge=1, le=MAX_ID)
    email: str = Field(...)
    username: Optional[str] = Field(default=None)
    roles: list[str] = Field(default_factory=list, max_length=MAX_ROLES)
    permissions: list[str] = Field(default_factory=list, max_length=MAX_PERMISSIONS)

    model_config = {
        "from_attributes": True,
        "frozen": True,
        "extra": "ignore",
    }

    @field_validator("email", mode="before")
    @classmethod
    def validate_email_shape(
            cls,
            value: str
    ) -> str:
        if value is None or not str(value).strip():
            raise ValueError("The email cannot be empty.")
        normalized = str(value).strip().lower()
        if len(normalized) > MAX_EMAIL_CHARS:
            raise ValueError(f"The email must not exceed {MAX_EMAIL_CHARS} characters.")
        if not _EMAIL_PATTERN.match(normalized):
            raise ValueError("The email format is invalid.")
        return normalized

    @field_validator("roles", mode="after")
    @classmethod
    def validate_role_lengths(
            cls,
            value: list[str]
    ) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for item in value:
            role = item.strip()
            if not role:
                raise ValueError("Role entries must not be blank.")
            if len(role) > MAX_ROLE_CHARS:
                raise ValueError(f"Each entry must not exceed {MAX_ROLE_CHARS} characters.")
            if role in seen:
                raise ValueError(f"Duplicate role detected: '{role}'.")
            seen.add(role)
            normalized.append(role)
        return normalized

    @field_validator("permissions", mode="after")
    @classmethod
    def validate_permission_lengths(
            cls,
            value: list[str]
    ) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for item in value:
            permission = item.strip()
            if not permission:
                raise ValueError("Permission entries must not be blank.")
            if len(permission) > MAX_PERMISSION_CHARS:
                raise ValueError(f"Each entry must not exceed {MAX_PERMISSION_CHARS} characters.")
            if permission in seen:
                raise ValueError(f"Duplicate permission detected: '{permission}'.")
            seen.add(permission)
            normalized.append(permission)
        return normalized
