import re
from typing import List
from pydantic import BaseModel, Field, model_validator

MAX_ID = 2_147_483_647
MAX_EMAIL_CHARS = 254
MAX_ROLE_CHARS = 100
MAX_PERMISSION_CHARS = 100
MAX_ROLES = 50
MAX_PERMISSIONS = 200

_EMAIL_PATTERN = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


class AuthenticatedUser(BaseModel):
    id: int = Field(..., gt=0, le=MAX_ID)
    email: str = Field(..., min_length=3, max_length=MAX_EMAIL_CHARS)
    roles: List[str] = Field(default_factory=list, max_length=MAX_ROLES)
    permissions: List[str] = Field(default_factory=list, max_length=MAX_PERMISSIONS)

    model_config = {
        "from_attributes": True
    }

    @model_validator(mode="after")
    def validate_fields(self) -> "AuthenticatedUser":
        email = self.email.strip().lower()
        if not _EMAIL_PATTERN.match(email):
            raise ValueError("email is not a valid email address.")
        self.email = email

        seen_roles: set[str] = set()
        clean_roles: list[str] = []
        for role in self.roles:
            role = role.strip()
            if not role:
                raise ValueError("Role entries must not be blank.")
            if len(role) > MAX_ROLE_CHARS:
                raise ValueError(f"Each role must not exceed {MAX_ROLE_CHARS} characters.")
            if role in seen_roles:
                raise ValueError(f"Duplicate role detected: '{role}'.")
            seen_roles.add(role)
            clean_roles.append(role)
        self.roles = clean_roles

        seen_perms: set[str] = set()
        clean_perms: list[str] = []
        for perm in self.permissions:
            perm = perm.strip()
            if not perm:
                raise ValueError("Permission entries must not be blank.")
            if len(perm) > MAX_PERMISSION_CHARS:
                raise ValueError(f"Each permission must not exceed {MAX_PERMISSION_CHARS} characters.")
            if perm in seen_perms:
                raise ValueError(f"Duplicate permission detected: '{perm}'.")
            seen_perms.add(perm)
            clean_perms.append(perm)
        self.permissions = clean_perms

        return self

    def has_role(self, role: str) -> bool:
        return role in set(self.roles)

    def has_any_role(self, roles: set[str]) -> bool:
        return bool(set(self.roles) & roles)

    def has_permission(self, permission: str) -> bool:
        return permission in set(self.permissions)

    def has_any_permission(self, permissions: set[str]) -> bool:
        return bool(set(self.permissions) & permissions)

    def has_all_permissions(self, permissions: set[str]) -> bool:
        return permissions.issubset(set(self.permissions))
