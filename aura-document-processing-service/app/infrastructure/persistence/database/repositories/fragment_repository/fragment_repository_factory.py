import logging

from app.infrastructure.persistence.database.repositories.fragment_repository.fragment_repository import (
    FragmentRepository
)
from app.infrastructure.persistence.database.repositories.fragment_repository.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface
)

logger = logging.getLogger(__name__)


def create_fragment_repository() -> FragmentRepositoryInterface:
    return FragmentRepository()
