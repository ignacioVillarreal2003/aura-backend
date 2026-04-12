from pydantic import BaseModel, Field


class AuthenticatedUserResponse(BaseModel):
    id: int = Field(...)
    email: str = Field(...)
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)

    model_config = {
        "from_attributes": True
    }