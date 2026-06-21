from dataclasses import dataclass, field


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    email: str
    username: str = ""
    roles: tuple[str, ...] = field(default_factory=tuple)
    permissions: tuple[str, ...] = field(default_factory=tuple)
    is_service: bool = False

    @property
    def pk(self) -> int:
        return self.id

    @property
    def is_authenticated(self) -> bool:
        return True

    def has_all_permissions(self, required: frozenset[str]) -> bool:
        if not required:
            return True
        return required <= set(self.permissions)
