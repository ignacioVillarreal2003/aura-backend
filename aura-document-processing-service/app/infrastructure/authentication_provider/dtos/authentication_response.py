from typing import List
from pydantic import BaseModel, Field


class AuthenticationResponse(BaseModel):
    id: int = Field(
        ...
    )
    email: str = Field(
        ...
    )
    roles: List[str] = Field(
        default_factory=list
    )
