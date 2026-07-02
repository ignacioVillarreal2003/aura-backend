import pytest
from unittest.mock import patch, MagicMock

from apps.notification.models import Notification, NotificationStatus
from core.models.soft_delete import SoftDeleteManager, SoftDeleteQuerySet


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
    return Notification(**defaults)


class TestSoftDeleteQuerySet:
    def test_alive_excludes_deleted(self):
        mock_qs = MagicMock(spec=SoftDeleteQuerySet)
        alive_qs = MagicMock()
        mock_qs.alive.return_value = alive_qs
        result = mock_qs.alive()
        assert result is alive_qs

    def test_dead_returns_only_deleted(self):
        mock_qs = MagicMock(spec=SoftDeleteQuerySet)
        dead_qs = MagicMock()
        mock_qs.dead.return_value = dead_qs
        result = mock_qs.dead()
        assert result is dead_qs

    def test_delete_calls_update_with_deleted_at(self):
        mock_qs = MagicMock(spec=SoftDeleteQuerySet)
        mock_qs.delete.return_value = (1, {})
        result = mock_qs.delete()
        mock_qs.delete.assert_called_once()

    def test_hard_delete_delegates_to_super_delete(self):
        mock_qs = MagicMock(spec=SoftDeleteQuerySet)
        mock_qs.hard_delete.return_value = (1, {"notification": 1})
        result = mock_qs.hard_delete()
        mock_qs.hard_delete.assert_called_once()

    def test_delete_accepts_deleted_by(self):
        mock_qs = MagicMock(spec=SoftDeleteQuerySet)
        mock_qs.delete.return_value = (1, {})
        mock_qs.delete(deleted_by=99)
        mock_qs.delete.assert_called_with(deleted_by=99)

    def test_alive_filters_null_deleted_at(self):
        qs = MagicMock()
        qs.filter.return_value = qs
        with patch.object(SoftDeleteQuerySet, "filter", return_value=qs) as mock_filter:
            sqm = SoftDeleteQuerySet.__new__(SoftDeleteQuerySet)
            sqm.filter = mock_filter
            sqm.alive()
        mock_filter.assert_called_with(deleted_at__isnull=True)

    def test_dead_excludes_null_deleted_at(self):
        qs = MagicMock()
        qs.exclude.return_value = qs
        with patch.object(SoftDeleteQuerySet, "exclude", return_value=qs) as mock_exclude:
            sqm = SoftDeleteQuerySet.__new__(SoftDeleteQuerySet)
            sqm.exclude = mock_exclude
            sqm.dead()
        mock_exclude.assert_called_with(deleted_at__isnull=True)


class TestSoftDeleteManager:
    def test_default_manager_returns_alive_queryset(self):
        inner_qs = MagicMock(spec=SoftDeleteQuerySet)
        alive_qs = MagicMock()
        inner_qs.alive.return_value = alive_qs
        manager = MagicMock(spec=SoftDeleteManager)
        manager.get_queryset.return_value = alive_qs
        result = manager.get_queryset()
        assert result is alive_qs

    def test_all_with_deleted_returns_full_queryset(self):
        manager = MagicMock(spec=SoftDeleteManager)
        all_qs = MagicMock()
        manager.all_with_deleted.return_value = all_qs
        result = manager.all_with_deleted()
        assert result is all_qs

    def test_deleted_only_returns_dead_queryset(self):
        manager = MagicMock(spec=SoftDeleteManager)
        dead_qs = MagicMock()
        manager.deleted_only.return_value = dead_qs
        result = manager.deleted_only()
        assert result is dead_qs

    def test_soft_delete_on_instance_sets_deleted_at(self):
        n = make_notification()
        with patch.object(n, "save"):
            n.soft_delete(deleted_by=1)
        assert n.deleted_at is not None

    def test_restore_on_instance_clears_deleted_at(self):
        from django.utils import timezone
        n = make_notification()
        n.deleted_at = timezone.now()
        with patch.object(n, "save"):
            n.restore()
        assert n.deleted_at is None
