import pytest


@pytest.fixture(scope="session", autouse=True)
def _create_unmanaged_tables(django_db_setup, django_db_blocker):
    from django.apps import apps as dj_apps
    from django.db import connection

    with django_db_blocker.unblock():
        existing = set(connection.introspection.table_names())
        with connection.schema_editor() as schema_editor:
            for model in dj_apps.get_app_config("notification").get_models():
                if not model._meta.managed and model._meta.db_table not in existing:
                    schema_editor.create_model(model)
