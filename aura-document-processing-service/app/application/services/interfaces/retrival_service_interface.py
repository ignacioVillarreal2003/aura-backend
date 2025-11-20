from typing import Protocol
from sqlalchemy.orm.session import Session

from app.domain.models.fragment import Fragment


class RetrivalServiceInterface(Protocol):
    def process_question(self,
                         question: str,
                         db: Session,
                         embedding_type: str,
                         k: int,
                         threshold: float) -> list[Fragment]:
        ...
