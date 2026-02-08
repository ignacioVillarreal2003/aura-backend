from pydantic import BaseModel, Field


class AuthenticationRequest(BaseModel):
    token: str = Field(
        ...
    )

    class Config:
        frozen = True
