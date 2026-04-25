from pydantic import BaseModel, Field, field_validator

_MAX_TOKEN_CHARS = 8192
_MIN_TOKEN_CHARS = 10


class UserAuthenticationRequest(BaseModel):
    token: str = Field(..., min_length=_MIN_TOKEN_CHARS, max_length=_MAX_TOKEN_CHARS)

    model_config = {
        "frozen": True,
        "extra": "forbid",
    }

    @field_validator("token", mode="before")
    @classmethod
    def validate_token(
            cls,
            value: str
    ) -> str:
        token = str(value or "").strip()
        if not token:
            raise ValueError("Token cannot be empty.")
        return token
