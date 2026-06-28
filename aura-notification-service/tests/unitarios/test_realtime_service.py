"""
Tests unitarios para RealtimeService.
Patchea publish_user_event para no tocar Redis.
"""
import pytest
from unittest.mock import patch, call

from apps.notification.services.realtime_service import RealtimeService

_PUBLISH = "apps.notification.services.realtime_service.publish_user_event"


svc = RealtimeService()


class TestRealtimeService:
    def test_publish_created_calls_publish_user_event(self):
        with patch(_PUBLISH) as mock_pub:
            svc.publish_created(1, {"id": 10})
        mock_pub.assert_called_once()

    def test_publish_created_includes_user_id(self):
        with patch(_PUBLISH) as mock_pub:
            svc.publish_created(99, {"id": 10})
        args, _ = mock_pub.call_args
        assert args[0] == 99

    def test_publish_updated_calls_publish_user_event(self):
        with patch(_PUBLISH) as mock_pub:
            svc.publish_updated(2, {"id": 20})
        mock_pub.assert_called_once()

    def test_publish_updated_includes_payload(self):
        with patch(_PUBLISH) as mock_pub:
            svc.publish_updated(2, {"id": 20, "status": "read"})
        _, kwargs = mock_pub.call_args
        args = mock_pub.call_args[0]
        assert args[1]["data"] == {"id": 20, "status": "read"}

    def test_publish_deleted_calls_publish_user_event(self):
        with patch(_PUBLISH) as mock_pub:
            svc.publish_deleted(3, notification_id=5)
        mock_pub.assert_called_once()

    def test_publish_deleted_includes_notification_id(self):
        with patch(_PUBLISH) as mock_pub:
            svc.publish_deleted(3, notification_id=5)
        args, _ = mock_pub.call_args
        assert args[1]["data"]["id"] == 5

    def test_publish_created_passes_full_payload_dict(self):
        payload = {"id": 1, "message": "hello", "event_type": "chat.member.invited"}
        with patch(_PUBLISH) as mock_pub:
            svc.publish_created(42, payload)
        args, _ = mock_pub.call_args
        assert args[1]["data"] == payload

    def test_event_type_constants_are_correct_strings(self):
        assert RealtimeService.EVENT_CREATED == "notification.created"
        assert RealtimeService.EVENT_UPDATED == "notification.updated"
        assert RealtimeService.EVENT_DELETED == "notification.deleted"

    def test_publish_created_wraps_payload_under_data_key(self):
        with patch(_PUBLISH) as mock_pub:
            svc.publish_created(1, {"id": 10})
        args, _ = mock_pub.call_args
        assert "data" in args[1]
        assert args[1]["event"] == "notification.created"

    def test_publish_deleted_wraps_id_under_data_key(self):
        with patch(_PUBLISH) as mock_pub:
            svc.publish_deleted(1, notification_id=7)
        args, _ = mock_pub.call_args
        assert args[1]["data"] == {"id": 7}
        assert args[1]["event"] == "notification.deleted"
