from collections.abc import Set as AbstractSet
from typing import Annotated
from pydantic import BaseModel, Field, PrivateAttr, StringConstraints

from app.domain.field_limits import (
    MAX_EMAIL_CHARS,
    MAX_PERMISSION_CHARS,
    MAX_PERMISSIONS,
    MAX_ROLE_CHARS,
    MAX_ROLES,
)
from app.domain.types import UserId

_Role = Annotated[str, StringConstraints(max_length=MAX_ROLE_CHARS)]
_Permission = Annotated[str, StringConstraints(max_length=MAX_PERMISSION_CHARS)]


class AuthenticatedUser(BaseModel):
    id: UserId = Field(...)
    email: str | None = Field(default=None, max_length=MAX_EMAIL_CHARS)
    roles: list[_Role] = Field(default_factory=list, max_length=MAX_ROLES)
    permissions: list[_Permission] = Field(default_factory=list, max_length=MAX_PERMISSIONS)

    _roles_set: frozenset[str] = PrivateAttr()
    _permissions_set: frozenset[str] = PrivateAttr()

    model_config = {
        "from_attributes": True,
        "frozen": True,
    }

    def model_post_init(self, __context: object) -> None:
        object.__setattr__(self, "_roles_set", frozenset(self.roles))
        object.__setattr__(self, "_permissions_set", frozenset(self.permissions))

    def has_role(self, role: str) -> bool:
        return role in self._roles_set

    def has_any_role(self, roles: AbstractSet[str]) -> bool:
        return bool(self._roles_set & roles)

    def has_permission(self, permission: str) -> bool:
        return permission in self._permissions_set

    def has_any_permission(self, permissions: AbstractSet[str]) -> bool:
        return bool(self._permissions_set & permissions)

    def has_all_permissions(self, permissions: AbstractSet[str]) -> bool:
        return self._permissions_set >= permissions
