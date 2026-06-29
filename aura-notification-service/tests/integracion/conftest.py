import pytest


@pytest.fixture(scope="session", autouse=True)
def _create_unmanaged_tables(django_db_setup, django_db_blocker):
    """Crea en el test DB (SQLite) las tablas de los modelos managed=False del
    app notification (notification, notification_preference, email_dispatch).

    En producción esas tablas las crea docker/database/aura-db/notification.sql,
    no las migraciones de Django, así que pytest-django nunca las arma. El
    schema_editor genera el DDL SQLite a partir del modelo. Los view tests
    mockean el service y no las usan, pero test_send_email_task crea filas reales.
    """
    from django.apps import apps as dj_apps
    from django.db import connection

    with django_db_blocker.unblock():
        existing = set(connection.introspection.table_names())
        with connection.schema_editor() as schema_editor:
            for model in dj_apps.get_app_config("notification").get_models():
                if not model._meta.managed and model._meta.db_table not in existing:
                    schema_editor.create_model(model)
