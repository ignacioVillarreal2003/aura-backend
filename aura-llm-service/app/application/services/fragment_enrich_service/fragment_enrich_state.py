from dataclasses import dataclass

from app.domain.authentication.authenticated_user import AuthenticatedUser


@dataclass(frozen=True)
class FragmentEnrichState:
    authenticated_user: AuthenticatedUser
    content: str
