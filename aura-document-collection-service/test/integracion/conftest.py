import pytest

from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.permissions import (
    ADD_DOCUMENT_COLLECTION_DOCUMENT,
    ADD_USER_COMPARTMENT,
    CREATE_CLASSIFICATION_LEVEL,
    CREATE_COMPARTMENT,
    CREATE_DOCUMENT_COLLECTION,
    DELETE_CLASSIFICATION_LEVEL,
    DELETE_COMPARTMENT,
    DELETE_DOCUMENT_COLLECTION,
    DELETE_USER_CLEARANCE,
    GET_CLASSIFICATION_LEVEL,
    GET_COMPARTMENT,
    GET_DOCUMENT_COLLECTION,
    GET_USER_ACCESSIBLE_COLLECTIONS,
    GET_USER_AUTHORIZATION,
    LIST_CLASSIFICATION_LEVELS,
    LIST_COMPARTMENTS,
    LIST_DOCUMENT_COLLECTION_DOCUMENTS,
    LIST_DOCUMENT_COLLECTIONS,
    LIST_USER_COMPARTMENTS,
    REMOVE_DOCUMENT_COLLECTION_DOCUMENT,
    REMOVE_USER_COMPARTMENT,
    SET_USER_CLEARANCE,
    UPDATE_CLASSIFICATION_LEVEL,
    UPDATE_COMPARTMENT,
    UPDATE_DOCUMENT_COLLECTION,
)

_ALL_PERMISSIONS = (
    LIST_DOCUMENT_COLLECTIONS,
    CREATE_DOCUMENT_COLLECTION,
    GET_DOCUMENT_COLLECTION,
    UPDATE_DOCUMENT_COLLECTION,
    DELETE_DOCUMENT_COLLECTION,
    LIST_DOCUMENT_COLLECTION_DOCUMENTS,
    ADD_DOCUMENT_COLLECTION_DOCUMENT,
    REMOVE_DOCUMENT_COLLECTION_DOCUMENT,
    LIST_CLASSIFICATION_LEVELS,
    CREATE_CLASSIFICATION_LEVEL,
    GET_CLASSIFICATION_LEVEL,
    UPDATE_CLASSIFICATION_LEVEL,
    DELETE_CLASSIFICATION_LEVEL,
    LIST_COMPARTMENTS,
    CREATE_COMPARTMENT,
    GET_COMPARTMENT,
    UPDATE_COMPARTMENT,
    DELETE_COMPARTMENT,
    GET_USER_AUTHORIZATION,
    SET_USER_CLEARANCE,
    DELETE_USER_CLEARANCE,
    LIST_USER_COMPARTMENTS,
    ADD_USER_COMPARTMENT,
    REMOVE_USER_COMPARTMENT,
    GET_USER_ACCESSIBLE_COLLECTIONS,
)


def make_user(id: int, **kwargs) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=id,
        email=f"user{id}@test.com",
        username=f"user{id}",
        permissions=_ALL_PERMISSIONS,
        **kwargs,
    )


@pytest.fixture(scope="session", autouse=True)
def _create_unmanaged_tables(django_db_setup, django_db_blocker):
    """Crea en el test DB las tablas de los modelos managed=False del servicio.

    En producción esas tablas las crea docker/database/aura-db/document_collection.sql
    (y la tabla `document`, otro servicio), no las migraciones de Django, así que
    pytest-django nunca las arma. schema_editor genera el DDL desde el modelo
    (matchea lo que el ORM inserta). Se crean en orden topológico de FKs.
    """
    from django.apps import apps as dj_apps
    from django.db import connection

    with django_db_blocker.unblock():
        existing = set(connection.introspection.table_names())
        pending = [
            m for m in dj_apps.get_models()
            if not m._meta.managed and m._meta.db_table not in existing
        ]
        created = set(existing)
        with connection.schema_editor() as schema_editor:
            progress = True
            while pending and progress:
                progress = False
                for model in list(pending):
                    deps = {
                        f.related_model._meta.db_table
                        for f in model._meta.get_fields()
                        if getattr(f, "many_to_one", False) and f.related_model is not None
                    }
                    if deps <= created:
                        schema_editor.create_model(model)
                        created.add(model._meta.db_table)
                        pending.remove(model)
                        progress = True
            for model in pending:  # fallback: ciclos o deps externas
                schema_editor.create_model(model)


@pytest.fixture
def admin():
    return make_user(id=1000)


@pytest.fixture
def other_user():
    return make_user(id=1001)
