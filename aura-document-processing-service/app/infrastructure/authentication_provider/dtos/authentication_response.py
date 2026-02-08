from typing import Optional, List
from pydantic import BaseModel, Field


class AuthenticationResponse(BaseModel):
    id: int = Field(
        ...
    )
    email: str = Field(
        ...
    )
    username: Optional[str] = Field(
        None
    )
    roles: List[str] = Field(
        default_factory=list
    )

    class Config:
        frozen = True

    def has_role(
            self,
            role: str
    ) -> bool:
        return role in self.roles

    def has_any_role(
            self,
            roles: List[str]
    ) -> bool:
        return any(role in self.roles for role in roles)

    def has_all_roles(
            self,
            roles: List[str]
    ) -> bool:
        return all(role in self.roles for role in roles)
