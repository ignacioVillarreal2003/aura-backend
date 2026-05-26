import logging

from django.db import connections
from django.utils import timezone

logger = logging.getLogger(__name__)


def sync_group_to_collection(group, actor_id: int, old_name: str = None, is_create: bool = False) -> None:
    try:
        with connections['aura_db'].cursor() as cursor:
            if old_name and old_name != group.name:
                cursor.execute(
                    """
                    UPDATE document_collection
                    SET name = %s, updated_by = %s, updated_at = %s
                    WHERE name = %s AND deleted_at IS NULL
                    """,
                    [group.name, actor_id, timezone.now(), old_name],
                )
                if cursor.rowcount == 0:
                    cursor.execute(
                        'INSERT INTO document_collection (name, created_by, created_at) VALUES (%s, %s, %s)',
                        [group.name, actor_id, timezone.now()],
                    )
                return

            cursor.execute(
                'SELECT id FROM document_collection WHERE name = %s AND deleted_at IS NULL',
                [group.name],
            )
            exists = cursor.fetchone() is not None
            if is_create and not exists:
                cursor.execute(
                    'INSERT INTO document_collection (name, created_by, created_at) VALUES (%s, %s, %s)',
                    [group.name, actor_id, timezone.now()],
                )
            elif exists:
                cursor.execute(
                    'UPDATE document_collection SET updated_by = %s, updated_at = %s WHERE name = %s AND deleted_at IS NULL',
                    [actor_id, timezone.now(), group.name],
                )
            else:
                cursor.execute(
                    'INSERT INTO document_collection (name, created_by, created_at) VALUES (%s, %s, %s)',
                    [group.name, actor_id, timezone.now()],
                )
    except Exception:
        logger.exception('Failed to sync CustomGroup to aura_db.document_collection')


def soft_delete_collection(group, actor_id: int) -> None:
    try:
        with connections['aura_db'].cursor() as cursor:
            cursor.execute(
                """
                UPDATE document_collection
                SET deleted_by = %s, deleted_at = %s
                WHERE name = %s AND deleted_at IS NULL
                """,
                [actor_id, timezone.now(), group.name],
            )
    except Exception:
        logger.exception('Failed to soft-delete document_collection in aura_db')
