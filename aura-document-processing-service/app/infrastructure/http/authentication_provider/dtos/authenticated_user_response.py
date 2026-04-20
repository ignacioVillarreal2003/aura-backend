import re

from pydantic import BaseModel, Field, field_validator

# Avoid pydantic.networks.EmailStr so the optional `email-validator` package is not required.
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthenticatedUserResponse(BaseModel):
    id: int = Field(..., ge=1, le=2_147_483_647)
    email: str = Field(...)
    roles: list[str] = Field(default_factory=list, max_length=50)
    permissions: list[str] = Field(default_factory=list, max_length=200)

    model_config = {
        "from_attributes": True
    }

    @field_validator("email", mode="before")
    @classmethod
    def validate_email_shape(
            cls,
            value: str
    ) -> str:
        if value is None or not str(value).strip():
            raise ValueError("The email cannot be empty.")
        normalized = str(value).strip()
        if not _EMAIL_PATTERN.match(normalized):
            raise ValueError("The email format is invalid.")
        return normalized

    @field_validator("roles", "permissions", mode="after")
    @classmethod
    def validate_entry_lengths(
            cls,
            value: list[str]
    ) -> list[str]:
        max_chars = 100
        for item in value:
            if len(item) > max_chars:
                raise ValueError(f"Each entry must not exceed {max_chars} characters.")
        return value
