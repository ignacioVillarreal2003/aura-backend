import logging

from django.conf import settings
from django.db import connections

from documents.services.document_processing_client import create_document_from_admin

logger = logging.getLogger(__name__)


def ensure_admin_chat(actor_user_id: int) -> int:
    admin_chat_id = settings.ADMIN_CHAT_ID
    with connections['aura_db'].cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO chat (id, name, created_by)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            [admin_chat_id, 'Carga administrativa de documentos', actor_user_id],
        )
    return admin_chat_id


def upload_document_for_admin(*, raw_document, actor_user) -> dict:
    chat_id = ensure_admin_chat(actor_user.pk)
    return create_document_from_admin(
        raw_document=raw_document,
        chat_id=chat_id,
        actor_user=actor_user,
    )
