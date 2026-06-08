import logging

from documents.services.document_processing_client import create_document_from_admin

logger = logging.getLogger(__name__)


def upload_document_for_admin(*, raw_document, actor_user) -> dict:
    return create_document_from_admin(
        raw_document=raw_document,
        actor_user=actor_user,
    )
