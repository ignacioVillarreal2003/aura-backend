"""
Tests unitarios para el modelo Notification.
Requiere la fixture django_db_setup del conftest de unitarios (managed=False → True).
"""
import pytest
from unittest.mock import patch, MagicMock

from apps.notification.models import Notification, NotificationStatus


def make_notification(**kwargs):
    defaults = dict(
        receiver_id=1,
        event_type="chat.member.invited",
        message="Test message",
        status=NotificationStatus.UNREAD,
        data={},
        severity="info",
    )
    defaults.update(kwargs)
    n = Notification(**defaults)
    return n


class TestMarkReadUnread:
    def test_mark_read_sets_status_read(self):
        n = make_notification()
        with patch.object(n, "save"):
            n.mark_read()
        assert n.status == NotificationStatus.READ

    def test_mark_read_sets_read_at(self):
        n = make_notification()
        with patch.object(n, "save"):
            n.mark_read()
        assert n.read_at is not None

    def test_mark_unread_sets_status_unread(self):
        n = make_notification(status=NotificationStatus.READ)
        with patch.object(n, "save"):
            n.mark_unread()
        assert n.status == NotificationStatus.UNREAD

    def test_mark_unread_clears_read_at(self):
        from django.utils import timezone
        n = make_notification(status=NotificationStatus.READ)
        n.read_at = timezone.now()
        with patch.object(n, "save"):
            n.mark_unread()
        assert n.read_at is None

    def test_mark_read_twice_idempotent(self):
        n = make_notification()
        with patch.object(n, "save"):
            n.mark_read()
            first_read_at = n.read_at
            n.mark_read()
        assert n.status == NotificationStatus.READ
        assert n.read_at is not None


class TestSoftDelete:
    def test_soft_delete_sets_deleted_at(self):
        n = make_notification()
        with patch.object(n, "save"):
            n.soft_delete(deleted_by=99)
        assert n.deleted_at is not None

    def test_soft_delete_sets_deleted_by(self):
        n = make_notification()
        with patch.object(n, "save"):
            n.soft_delete(deleted_by=99)
        assert n.deleted_by == 99

    def test_is_deleted_true_after_soft_delete(self):
        n = make_notification()
        with patch.object(n, "save"):
            n.soft_delete()
        assert n.is_deleted is True

    def test_restore_clears_deleted_at_and_deleted_by(self):
        from django.utils import timezone
        n = make_notification()
        n.deleted_at = timezone.now()
        n.deleted_by = 1
        with patch.object(n, "save"):
            n.restore()
        assert n.deleted_at is None
        assert n.deleted_by is None

    def test_is_deleted_false_before_soft_delete(self):
        n = make_notification()
        assert n.is_deleted is False


class TestStr:
    def test_str_includes_event_type(self):
        n = make_notification(event_type="auth.password.changed")
        assert "auth.password.changed" in str(n)

    def test_str_includes_receiver_id(self):
        n = make_notification(receiver_id=42)
        assert "42" in str(n)


class TestStatusChoices:
    def test_unread_value(self):
        assert NotificationStatus.UNREAD == "unread"

    def test_read_value(self):
        assert NotificationStatus.READ == "read"
