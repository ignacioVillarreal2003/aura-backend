"""Acceso a datos de la asignacion MAC de un documento, sobre aura_db."""
from django.db import connections


def _get_doc_mac_assignments(doc_id):
    """Devuelve (nivel_actual, conjunto_de_agrupaciones) de un documento."""
    current_level_id = None
    current_comp_ids = set()
    try:
        with connections['aura_db'].cursor() as cursor:
            cursor.execute("""
                SELECT dc.classification_level_id
                FROM document_in_document_collection dic
                JOIN document_collection dc ON dic.document_collection_id = dc.id
                WHERE dic.document_id = %s
                  AND dic.deleted_at IS NULL
                  AND dc.deleted_at IS NULL
                  AND dc.classification_level_id IS NOT NULL
                LIMIT 1
            """, [doc_id])
            row = cursor.fetchone()
            if row:
                current_level_id = row[0]
            cursor.execute("""
                SELECT DISTINCT dcc.compartment_id
                FROM document_in_document_collection dic
                JOIN document_collection dc ON dic.document_collection_id = dc.id
                JOIN document_collection_compartment dcc ON dcc.document_collection_id = dc.id
                WHERE dic.document_id = %s
                  AND dic.deleted_at IS NULL
                  AND dc.deleted_at IS NULL
            """, [doc_id])
            current_comp_ids = {row[0] for row in cursor.fetchall()}
    except Exception:
        pass
    return current_level_id, current_comp_ids


def _db_assign_strict_mac_collection(doc_id, level_id, comp_ids, actor_user_id):
    """Asigna el documento a una unica coleccion MAC y quita los vinculos viejos."""
    if level_id is None:
        return

    sorted_ids = sorted(comp_ids)
    if sorted_ids:
        key = '_'.join(str(i) for i in sorted_ids)
        name = f'__mac_{level_id}_comp_{key}__'
    else:
        name = f'__mac_{level_id}__'

    with connections['aura_db'].cursor() as cursor:
        cursor.execute(
            "SELECT id FROM document_collection WHERE name = %s AND deleted_at IS NULL LIMIT 1",
            [name],
        )
        row = cursor.fetchone()
        if row:
            col_id = row[0]
        else:
            cursor.execute(
                """INSERT INTO document_collection (name, classification_level_id, created_by, created_at)
                   VALUES (%s, %s, %s, NOW()) RETURNING id""",
                [name, level_id, actor_user_id],
            )
            col_id = cursor.fetchone()[0]
            for comp_id in sorted_ids:
                cursor.execute(
                    """INSERT INTO document_collection_compartment
                           (document_collection_id, compartment_id, created_by, created_at)
                       VALUES (%s, %s, %s, NOW())
                       ON CONFLICT ON CONSTRAINT doc_coll_comp_coll_compartment_unique DO NOTHING""",
                    [col_id, comp_id, actor_user_id],
                )

        cursor.execute(
            """
            INSERT INTO document_in_document_collection
                (document_collection_id, document_id, created_by, created_at)
            SELECT %s, %s, %s, NOW()
            WHERE NOT EXISTS (
                SELECT 1 FROM document_in_document_collection
                WHERE document_collection_id = %s AND document_id = %s AND deleted_at IS NULL
            )
            """,
            [col_id, doc_id, actor_user_id, col_id, doc_id],
        )

        cursor.execute(
            """UPDATE document_in_document_collection
               SET deleted_at = NOW(), deleted_by = %s
               WHERE document_id = %s
                 AND deleted_at IS NULL
                 AND document_collection_id != %s
                 AND document_collection_id IN (
                     SELECT id FROM document_collection
                     WHERE (LEFT(name, 6) = '__mac_'
                         OR LEFT(name, 14) = '__admin_level_'
                         OR LEFT(name, 13) = '__admin_comp_')
                       AND deleted_at IS NULL
                 )""",
            [actor_user_id, doc_id, col_id],
        )
