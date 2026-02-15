import logging

from app.infrastructure.persistence.database.repositories.document_repository.document_repository import (
    DocumentRepository
)
from app.infrastructure.persistence.database.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface
)

logger = logging.getLogger(__name__)


def create_document_repository() -> DocumentRepositoryInterface:
    return DocumentRepository()
