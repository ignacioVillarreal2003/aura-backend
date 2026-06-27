"""Acceso a la tabla local document_admin_meta.

El servicio de procesamiento pisa la descripcion de los documentos, asi que el
admin guarda su propio nombre y descripcion en esta tabla aparte.
"""
from django.db import connections

_meta_table_ensured = False


def _ensure_meta_table():
    global _meta_table_ensured
    if _meta_table_ensured:
        return
    try:
        with connections['default'].cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS document_admin_meta (
                    document_id BIGINT PRIMARY KEY,
                    admin_name  VARCHAR(255) NOT NULL DEFAULT '',
                    admin_description TEXT NOT NULL DEFAULT ''
                )
            """)
        _meta_table_ensured = True
    except Exception:
        pass


def _save_doc_meta(doc_id, name, description):
    _ensure_meta_table()
    try:
        with connections['default'].cursor() as cursor:
            cursor.execute("""
                INSERT INTO document_admin_meta (document_id, admin_name, admin_description)
                VALUES (%s, %s, %s)
                ON CONFLICT (document_id) DO UPDATE
                SET admin_name = EXCLUDED.admin_name,
                    admin_description = EXCLUDED.admin_description
            """, [doc_id, name or '', description or ''])
    except Exception:
        pass


def _get_doc_meta(doc_id):
    _ensure_meta_table()
    try:
        with connections['default'].cursor() as cursor:
            cursor.execute(
                "SELECT admin_name, admin_description FROM document_admin_meta WHERE document_id = %s",
                [doc_id],
            )
            row = cursor.fetchone()
            return {'name': row[0], 'description': row[1]} if row else None
    except Exception:
        return None


def _batch_get_doc_meta_all():
    _ensure_meta_table()
    try:
        with connections['default'].cursor() as cursor:
            cursor.execute(
                "SELECT document_id, admin_name, admin_description FROM document_admin_meta"
            )
            return {row[0]: {'name': row[1], 'description': row[2]} for row in cursor.fetchall()}
    except Exception:
        return {}
