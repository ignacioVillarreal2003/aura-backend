from typing import List
from pydantic import BaseModel, Field


class AuthenticatedUserResponse(BaseModel):
    id: int = Field(...)
    email: str = Field(...)
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)

    model_config = {
        "from_attributes": True
    }