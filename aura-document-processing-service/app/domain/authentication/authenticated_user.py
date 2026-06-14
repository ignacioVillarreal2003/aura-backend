from typing import Optional
from pydantic import BaseModel, Field, PrivateAttr

from app.domain.types import UserId


class AuthenticatedUser(BaseModel):
    id: UserId = Field(...)
    # Optional because system-initiated principals (e.g. an outbox reconcile job
    # with no request context) carry only the owner's id. Real authenticated users
    # always have an email, enforced by the auth service response DTO.
    email: Optional[str] = Field(default=None)
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)

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

    def has_any_role(self, roles: set[str]) -> bool:
        return bool(self._roles_set & roles)

    def has_permission(self, permission: str) -> bool:
        return permission in self._permissions_set

    def has_any_permission(self, permissions: set[str]) -> bool:
        return bool(self._permissions_set & permissions)

    def has_all_permissions(self, permissions: set[str]) -> bool:
        return permissions.issubset(self._permissions_set)
