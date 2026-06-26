"""MAC (Mandatory Access Control) data & service access for the admin.

Extracted verbatim from accounts/admin_parts/mac_admin.py (M9: keep the admin
thin — presentation in the admin, data/service access here). Two kinds of
helpers live here, both used by the MAC admin views:

* direct ``aura_db`` SQL (collection / level / compartment <-> document links);
* document-collection service calls via ``mac_client``.

Behaviour is unchanged.
"""
import logging

from accounts.services.mac_client import MacServiceError, mac_client

logger = logging.getLogger(__name__)


def _delete_collections_for_level(user, level_id):
    """Null out the level FK on all collections (including soft-deleted) so the level can be hard-deleted."""
    from django.db import connections
    with connections['aura_db'].cursor() as cursor:
        cursor.execute(
            'UPDATE document_collection SET classification_level_id = NULL WHERE classification_level_id = %s',
            [level_id],
        )


def _delete_collections_for_comp(user, compartment_id):
    """Remove all junction rows for this compartment so it can be hard-deleted."""
    from django.db import connections
    with connections['aura_db'].cursor() as cursor:
        cursor.execute(
            'DELETE FROM document_collection_compartment WHERE compartment_id = %s',
            [compartment_id],
        )


def _get_all_level_doc_ids():
    """Return set of document IDs already assigned to any classification level collection."""
    from django.db import connections
    try:
        with connections['aura_db'].cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT dc_doc.document_id
                FROM document_in_document_collection dc_doc
                JOIN document_collection dc ON dc_doc.document_collection_id = dc.id
                WHERE dc.classification_level_id IS NOT NULL
                  AND dc_doc.deleted_at IS NULL
                  AND dc.deleted_at IS NULL
                """,
            )
            return {row[0] for row in cursor.fetchall()}
    except Exception:
        return set()


def _get_level_doc_ids(level_id):
    """Return set of document IDs in any collection at this classification level."""
    from django.db import connections
    try:
        with connections['aura_db'].cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT dc_doc.document_id
                FROM document_in_document_collection dc_doc
                JOIN document_collection dc ON dc_doc.document_collection_id = dc.id
                WHERE dc.classification_level_id = %s
                  AND dc_doc.deleted_at IS NULL
                  AND dc.deleted_at IS NULL
                """,
                [level_id],
            )
            return {row[0] for row in cursor.fetchall()}
    except Exception:
        return set()


def _get_comp_doc_ids(compartment_id):
    """Return set of document IDs in any collection that has this compartment."""
    from django.db import connections
    try:
        with connections['aura_db'].cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT dc_doc.document_id
                FROM document_in_document_collection dc_doc
                JOIN document_collection dc ON dc_doc.document_collection_id = dc.id
                JOIN document_collection_compartment dcc
                  ON dcc.document_collection_id = dc.id
                WHERE dcc.compartment_id = %s
                  AND dc_doc.deleted_at IS NULL
                  AND dc.deleted_at IS NULL
                """,
                [compartment_id],
            )
            return {row[0] for row in cursor.fetchall()}
    except Exception:
        return set()


def _db_ensure_mac_collection(level_id, comp_ids, actor_user_id):
    """Find or create a combined MAC collection with both a classification level and compartments."""
    from django.db import connections
    sorted_ids = sorted(comp_ids)
    key = '_'.join(str(i) for i in sorted_ids)
    name = f'__mac_{level_id}_{key}__'
    with connections['aura_db'].cursor() as cursor:
        cursor.execute(
            "SELECT id FROM document_collection WHERE name = %s AND deleted_at IS NULL LIMIT 1",
            [name],
        )
        row = cursor.fetchone()
        if row:
            return row[0]
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
        return col_id


def _db_link_doc_direct(collection_id, document_id, actor_user_id):
    """Link a document to a collection (idempotent) via direct DB insert."""
    from django.db import connections
    with connections['aura_db'].cursor() as cursor:
        cursor.execute(
            """INSERT INTO document_in_document_collection
                   (document_collection_id, document_id, created_by, created_at)
               SELECT %s, %s, %s, NOW()
               WHERE NOT EXISTS (
                   SELECT 1 FROM document_in_document_collection
                   WHERE document_collection_id = %s AND document_id = %s AND deleted_at IS NULL
               )""",
            [collection_id, document_id, actor_user_id, collection_id, document_id],
        )


def _db_sync_mac_collection_for_doc(doc_id, actor_user_id):
    """Rebuild the combined MAC collection link based on current admin single-dimension assignments."""
    from django.db import connections
    try:
        with connections['aura_db'].cursor() as cursor:
            cursor.execute(
                """UPDATE document_in_document_collection
                   SET deleted_at = NOW(), deleted_by = %s
                   WHERE document_id = %s
                     AND deleted_at IS NULL
                     AND document_collection_id IN (
                         SELECT id FROM document_collection
                         WHERE LEFT(name, 6) = '__mac_' AND deleted_at IS NULL
                     )""",
                [actor_user_id, doc_id],
            )
            cursor.execute(
                """SELECT dc.classification_level_id
                   FROM document_in_document_collection dic
                   JOIN document_collection dc ON dic.document_collection_id = dc.id
                   WHERE dic.document_id = %s
                     AND dic.deleted_at IS NULL
                     AND dc.deleted_at IS NULL
                     AND LEFT(dc.name, 14) = '__admin_level_'
                     AND dc.classification_level_id IS NOT NULL
                   LIMIT 1""",
                [doc_id],
            )
            level_row = cursor.fetchone()
            if not level_row:
                return
            level_id = level_row[0]
            cursor.execute(
                """SELECT DISTINCT dcc.compartment_id
                   FROM document_in_document_collection dic
                   JOIN document_collection dc ON dic.document_collection_id = dc.id
                   JOIN document_collection_compartment dcc ON dcc.document_collection_id = dc.id
                   WHERE dic.document_id = %s
                     AND dic.deleted_at IS NULL
                     AND dc.deleted_at IS NULL
                     AND LEFT(dc.name, 13) = '__admin_comp_'""",
                [doc_id],
            )
            comp_ids = frozenset(row[0] for row in cursor.fetchall())
        if comp_ids:
            col_id = _db_ensure_mac_collection(level_id, comp_ids, actor_user_id)
            _db_link_doc_direct(col_id, doc_id, actor_user_id)
    except Exception:
        logger.warning('Failed to sync MAC collection for doc %s', doc_id)


def _get_or_create_admin_collection_for_level(user, level_id, level_name):
    """Find or create the dedicated admin collection for a classification level."""
    admin_name = f'__admin_level_{level_id}__'
    try:
        collections = mac_client.list_document_collections(user)
        for col in collections:
            if col.get('name') == admin_name:
                return col
        return mac_client.create_document_collection(
            user, admin_name,
            classification_level_id=level_id,
            compartment_ids=[],
        )
    except MacServiceError:
        raise


def _get_or_create_admin_collection_for_comp(user, compartment_id):
    """Find or create the dedicated admin collection for a compartment.

    The document collection API requires a classification_level_id on every
    collection, so we use the lowest-rank available level as a technical
    requirement. The actual access control for the document is governed by
    the compartment membership, not by this level.
    """
    admin_name = f'__admin_comp_{compartment_id}__'
    try:
        collections = mac_client.list_document_collections(user)
        for col in collections:
            if col.get('name') == admin_name:
                return col
        levels = mac_client.list_classification_levels(user)
        if not levels:
            raise MacServiceError(
                'No hay niveles de clasificación disponibles. '
                'Cree al menos un nivel antes de asignar documentos a agrupaciones.'
            )
        lowest_level = min(levels, key=lambda l: l.get('rank', 0))
        return mac_client.create_document_collection(
            user, admin_name,
            classification_level_id=lowest_level['id'],
            compartment_ids=[compartment_id],
        )
    except MacServiceError:
        raise


def _remove_doc_from_level_collections(user, doc_id, level_id):
    """Remove a document from all collections at the given classification level."""
    from django.db import connections
    try:
        with connections['aura_db'].cursor() as cursor:
            cursor.execute(
                """
                SELECT dc_doc.document_collection_id
                FROM document_in_document_collection dc_doc
                JOIN document_collection dc ON dc_doc.document_collection_id = dc.id
                WHERE dc_doc.document_id = %s
                  AND dc.classification_level_id = %s
                  AND dc_doc.deleted_at IS NULL
                  AND dc.deleted_at IS NULL
                """,
                [doc_id, level_id],
            )
            col_ids = [row[0] for row in cursor.fetchall()]
    except Exception:
        col_ids = []
    errors = []
    for col_id in col_ids:
        try:
            mac_client.remove_document_from_collection(user, col_id, doc_id)
        except MacServiceError as exc:
            errors.append(str(exc))
    return errors


def _remove_doc_from_comp_collections(user, doc_id, compartment_id):
    """Remove a document from all collections that have the given compartment."""
    from django.db import connections
    try:
        with connections['aura_db'].cursor() as cursor:
            cursor.execute(
                """
                SELECT dc_doc.document_collection_id
                FROM document_in_document_collection dc_doc
                JOIN document_collection dc ON dc_doc.document_collection_id = dc.id
                JOIN document_collection_compartment dcc
                  ON dcc.document_collection_id = dc.id
                WHERE dc_doc.document_id = %s
                  AND dcc.compartment_id = %s
                  AND dc_doc.deleted_at IS NULL
                  AND dc.deleted_at IS NULL
                """,
                [doc_id, compartment_id],
            )
            col_ids = [row[0] for row in cursor.fetchall()]
    except Exception:
        col_ids = []
    errors = []
    for col_id in col_ids:
        try:
            mac_client.remove_document_from_collection(user, col_id, doc_id)
        except MacServiceError as exc:
            errors.append(str(exc))
    return errors
