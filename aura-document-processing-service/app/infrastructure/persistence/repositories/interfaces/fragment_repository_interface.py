from typing import Protocol
from sqlalchemy.orm import Session

from app.domain.models.fragment import Fragment


class FragmentRepositoryInterface(Protocol):
    def create(self,
               fragment: Fragment,
               db: Session) -> Fragment:
        ...