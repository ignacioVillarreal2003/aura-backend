from typing import List
from pydantic import BaseModel, Field


class AuthenticatedUser(BaseModel):
    id: int = Field(...)
    email: str = Field(...)
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)

    model_config = {
        "from_attributes": True
    }

    def has_role(
            self,
            role: str
    ) -> bool:
        return role in set(self.roles)

    def has_any_role(
            self,
            roles: set[str]
    ) -> bool:
        return bool(set(self.roles) & roles)

    def has_permission(
            self,
            permission: str
    ) -> bool:
        return permission in set(self.permissions)

    def has_any_permission(
            self,
            permissions: set[str]
    ) -> bool:
        return bool(set(self.permissions) & permissions)

    def has_all_permissions(
            self,
            permissions: set[str]
    ) -> bool:
        return permissions.issubset(set(self.permissions))
