import pytest
from django.db import connection


@pytest.fixture(scope="session")
def django_db_setup(django_test_environment, django_db_blocker):
    from apps.notification.models.notification import Notification
    from apps.notification.models.preference import NotificationPreference
    from apps.notification.models.dispatch import EmailDispatch

    models = [Notification, NotificationPreference, EmailDispatch]

    with django_db_blocker.unblock():
        for m in models:
            m._meta.managed = True
        with connection.schema_editor() as editor:
            for m in models:
                editor.create_model(m)
        yield
        with connection.schema_editor() as editor:
            for m in reversed(models):
                editor.delete_model(m)
        for m in models:
            m._meta.managed = False
