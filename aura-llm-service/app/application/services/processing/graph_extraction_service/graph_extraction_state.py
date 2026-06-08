from dataclasses import dataclass
from typing import Optional

from app.domain.authentication.authenticated_user import AuthenticatedUser


@dataclass(frozen=True)
class GraphExtractionState:
    authenticated_user: AuthenticatedUser
    content: str
    document_id: int
    fragment_id: int
    allowed_entity_types: tuple[str, ...]
    allowed_relation_types: Optional[tuple[str, ...]]
    max_entities: int
    max_relations: int
