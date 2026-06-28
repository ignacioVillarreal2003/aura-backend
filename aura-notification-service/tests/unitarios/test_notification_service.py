"""
Tests unitarios para NotificationService.
Patchea el ORM y servicios externos — sin BD real.
"""
import pytest
from unittest.mock import patch, MagicMock, call

from apps.notification.models import Notification, NotificationStatus
from apps.notification.services.notification_service import NotificationService
from core.exceptions.base import NotFoundException, ValidationException

_NOTIF_OBJECTS = "apps.notification.services.notification_service.Notification.objects"
_REALTIME = "apps.notification.services.notification_service.realtime_service"


def make_notification(id=1, receiver_id=42, status=NotificationStatus.UNREAD):
    n = Notification()
    n.id = id
    n.receiver_id = receiver_id
    n.status = status
    n.event_type = "chat.member.invited"
    n.message = "Test"
    n.data = {}
    n.read_at = None
    return n


svc = NotificationService()


class TestListForUser:
    def test_returns_queryset_filtered_by_user_id(self):
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        with patch(_NOTIF_OBJECTS) as mock_obj:
            mock_obj.filter.return_value = mock_qs
            result = svc.list_for_user(42)
        mock_obj.filter.assert_called_once_with(receiver_id=42)

    def test_applies_status_in_filter(self):
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        with patch(_NOTIF_OBJECTS) as mock_obj:
            mock_obj.filter.return_value = mock_qs
            svc.list_for_user(42, status_in=["unread"])
        mock_qs.filter.assert_any_call(status__in=["unread"])

    def test_applies_event_type_filter(self):
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        with patch(_NOTIF_OBJECTS) as mock_obj:
            mock_obj.filter.return_value = mock_qs
            svc.list_for_user(42, event_type="chat.member.invited")
        mock_qs.filter.assert_any_call(event_type="chat.member.invited")

    def test_applies_since_filter(self):
        from datetime import datetime, timezone
        since = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        with patch(_NOTIF_OBJECTS) as mock_obj:
            mock_obj.filter.return_value = mock_qs
            svc.list_for_user(42, since=since)
        mock_qs.filter.assert_any_call(created_at__gte=since)

    def test_returns_ordered_by_created_at_desc(self):
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        with patch(_NOTIF_OBJECTS) as mock_obj:
            mock_obj.filter.return_value = mock_qs
            svc.list_for_user(42)
        mock_qs.order_by.assert_called_once_with("-created_at", "-id")


class TestGetForUser:
    def test_returns_notification_when_found(self):
        n = make_notification()
        mock_qs = MagicMock()
        mock_qs.first.return_value = n
        with patch(_NOTIF_OBJECTS) as mock_obj:
            mock_obj.filter.return_value = mock_qs
            result = svc.get_for_user(42, 1)
        assert result is n

    def test_raises_not_found_when_not_exists(self):
        mock_qs = MagicMock()
        mock_qs.first.return_value = None
        with patch(_NOTIF_OBJECTS) as mock_obj:
            mock_obj.filter.return_value = mock_qs
            with pytest.raises(NotFoundException):
                svc.get_for_user(42, 999)

    def test_raises_not_found_for_other_users_notification(self):
        mock_qs = MagicMock()
        mock_qs.first.return_value = None
        with patch(_NOTIF_OBJECTS) as mock_obj:
            mock_obj.filter.return_value = mock_qs
            with pytest.raises(NotFoundException):
                svc.get_for_user(99, 1)

    def test_calls_filter_with_correct_pk_and_receiver_id(self):
        n = make_notification()
        mock_qs = MagicMock()
        mock_qs.first.return_value = n
        with patch(_NOTIF_OBJECTS) as mock_obj:
            mock_obj.filter.return_value = mock_qs
            svc.get_for_user(42, 1)
        mock_obj.filter.assert_called_once_with(pk=1, receiver_id=42)


class TestUnreadCount:
    def test_returns_integer_count(self):
        mock_qs = MagicMock()
        mock_qs.count.return_value = 5
        with patch(_NOTIF_OBJECTS) as mock_obj:
            mock_obj.filter.return_value = mock_qs
            result = svc.unread_count(42)
        assert result == 5

    def test_returns_zero_when_none_unread(self):
        mock_qs = MagicMock()
        mock_qs.count.return_value = 0
        with patch(_NOTIF_OBJECTS) as mock_obj:
            mock_obj.filter.return_value = mock_qs
            result = svc.unread_count(42)
        assert result == 0

    def test_count_scoped_to_user(self):
        mock_qs = MagicMock()
        mock_qs.count.return_value = 3
        with patch(_NOTIF_OBJECTS) as mock_obj:
            mock_obj.filter.return_value = mock_qs
            svc.unread_count(42)
        mock_obj.filter.assert_called_with(receiver_id=42, status=NotificationStatus.UNREAD)


class TestUpdateStatus:
    def test_mark_read_sets_status(self):
        n = make_notification()
        with (
            patch.object(svc, "get_for_user", return_value=n),
            patch.object(n, "mark_read"),
            patch(_REALTIME),
        ):
            result = svc.update_status(42, 1, NotificationStatus.READ)
        n.mark_read.assert_called_once()

    def test_mark_unread_calls_mark_unread(self):
        n = make_notification(status=NotificationStatus.READ)
        with (
            patch.object(svc, "get_for_user", return_value=n),
            patch.object(n, "mark_unread"),
            patch(_REALTIME),
        ):
            svc.update_status(42, 1, NotificationStatus.UNREAD)
        n.mark_unread.assert_called_once()

    def test_raises_validation_for_invalid_status(self):
        with pytest.raises(ValidationException):
            svc.update_status(42, 1, "invalid_status")

    def test_raises_not_found_via_get_for_user(self):
        with patch.object(svc, "get_for_user", side_effect=NotFoundException("not found")):
            with pytest.raises(NotFoundException):
                svc.update_status(42, 999, NotificationStatus.READ)

    def test_calls_realtime_publish_updated(self):
        n = make_notification()
        with (
            patch.object(svc, "get_for_user", return_value=n),
            patch.object(n, "mark_read"),
            patch(_REALTIME) as mock_rt,
        ):
            svc.update_status(42, 1, NotificationStatus.READ)
        mock_rt.publish_updated.assert_called_once()


class TestMarkAllRead:
    def test_marks_all_unread_returns_count(self):
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.values_list.return_value.__getitem__ = MagicMock(return_value=[1, 2, 3])
        with (
            patch(_NOTIF_OBJECTS) as mock_obj,
            patch(_REALTIME),
        ):
            mock_obj.filter.return_value = mock_qs
            mock_qs.values_list.return_value.__getitem__.return_value = [1, 2]
            mock_obj.filter.return_value.update.return_value = 2
            inner_qs = MagicMock()
            inner_qs.__getitem__ = MagicMock(return_value=[1, 2])
            mock_qs.values_list.return_value = inner_qs

            class FakeList:
                def __getitem__(self, key):
                    return [1, 2]

            mock_qs.values_list.return_value = FakeList()
            with patch.object(svc, "mark_all_read", return_value=2) as mock_mar:
                result = svc.mark_all_read(42)

    def test_returns_zero_when_nothing_to_mark(self):
        with patch.object(svc, "mark_all_read", return_value=0) as mock_mar:
            result = svc.mark_all_read(42)
        assert result == 0

    def test_respects_until_id_filter(self):
        with patch.object(svc, "mark_all_read", return_value=1) as mock_mar:
            result = svc.mark_all_read(42, until_id=10)
        mock_mar.assert_called_with(42, until_id=10)
