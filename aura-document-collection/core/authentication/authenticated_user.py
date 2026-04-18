from dataclasses import dataclass, field


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    email: str
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)

    @property
    def pk(self) -> int:
        return self.id

    @property
    def is_authenticated(self) -> bool:
        return True
