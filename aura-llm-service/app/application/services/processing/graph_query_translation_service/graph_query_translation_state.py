from dataclasses import dataclass

from app.domain.authentication.authenticated_user import AuthenticatedUser


@dataclass(frozen=True)
class GraphQueryTranslationState:
    authenticated_user: AuthenticatedUser
    question: str
    entity_types: tuple[str, ...]
    relation_types: tuple[str, ...]
