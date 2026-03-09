from pydantic import BaseModel, Field


class AuthenticationRequest(BaseModel):
    token: str = Field(
        ...
    )
