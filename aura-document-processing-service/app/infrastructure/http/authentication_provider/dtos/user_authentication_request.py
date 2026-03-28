from pydantic import BaseModel, Field


class UserAuthenticationRequest(BaseModel):
    token: str = Field(...)
