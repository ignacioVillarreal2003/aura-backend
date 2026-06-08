from dataclasses import dataclass

from app.domain.authentication.authenticated_user import AuthenticatedUser


@dataclass(frozen=True)
class DocumentClassifyState:
    authenticated_user: AuthenticatedUser
    document_name: str
    content: str
