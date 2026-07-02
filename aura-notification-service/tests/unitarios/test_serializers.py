import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from apps.notification.api.serializers.notification import (
    NotificationStatusUpdateSerializer,
    MarkAllReadRequestSerializer,
)
from apps.notification.api.serializers.preferences import NotificationPreferenceUpdateSerializer
from apps.notification.api.serializers.events import EventEmissionRequestSerializer

FUTURE = datetime(2099, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
PAST = datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


class TestNotificationStatusUpdateSerializer:
    def test_valid_status_read(self):
        s = NotificationStatusUpdateSerializer(data={"status": "read"})
        assert s.is_valid(), s.errors

    def test_valid_status_unread(self):
        s = NotificationStatusUpdateSerializer(data={"status": "unread"})
        assert s.is_valid(), s.errors

    def test_invalid_status_fails(self):
        s = NotificationStatusUpdateSerializer(data={"status": "pending"})
        assert not s.is_valid()
        assert "status" in s.errors

    def test_missing_status_fails(self):
        s = NotificationStatusUpdateSerializer(data={})
        assert not s.is_valid()
        assert "status" in s.errors


class TestMarkAllReadRequestSerializer:
    def test_valid_until_id(self):
        s = MarkAllReadRequestSerializer(data={"until_id": 100})
        assert s.is_valid(), s.errors

    def test_missing_until_id_is_optional(self):
        s = MarkAllReadRequestSerializer(data={})
        assert s.is_valid(), s.errors

    def test_zero_until_id_fails(self):
        s = MarkAllReadRequestSerializer(data={"until_id": 0})
        assert not s.is_valid()
        assert "until_id" in s.errors

    def test_negative_until_id_fails(self):
        s = MarkAllReadRequestSerializer(data={"until_id": -5})
        assert not s.is_valid()
        assert "until_id" in s.errors


class TestNotificationPreferenceUpdateSerializer:
    def test_email_enabled_false_valid(self):
        s = NotificationPreferenceUpdateSerializer(data={"email_enabled": False})
        assert s.is_valid(), s.errors

    def test_future_mute_until_valid(self):
        s = NotificationPreferenceUpdateSerializer(
            data={"mute_until": FUTURE.isoformat()}
        )
        assert s.is_valid(), s.errors

    def test_past_mute_until_invalid(self):
        s = NotificationPreferenceUpdateSerializer(
            data={"mute_until": PAST.isoformat()}
        )
        assert not s.is_valid()
        assert "mute_until" in s.errors

    def test_null_mute_until_valid(self):
        s = NotificationPreferenceUpdateSerializer(data={"mute_until": None})
        assert s.is_valid(), s.errors


class TestEventEmissionRequestSerializer:
    def test_known_event_type_valid(self):
        s = EventEmissionRequestSerializer(
            data={
                "event_type": "chat.member.invited",
                "recipient_ids": [1, 2],
            }
        )
        assert s.is_valid(), s.errors

    def test_unknown_event_type_invalid(self):
        s = EventEmissionRequestSerializer(
            data={
                "event_type": "no.such.event",
                "recipient_ids": [1],
            }
        )
        assert not s.is_valid()
        assert "event_type" in s.errors

    def test_empty_recipients_invalid(self):
        s = EventEmissionRequestSerializer(
            data={
                "event_type": "chat.member.invited",
                "recipient_ids": [],
            }
        )
        assert not s.is_valid()
        assert "recipient_ids" in s.errors

    def test_too_many_recipients_invalid(self):
        s = EventEmissionRequestSerializer(
            data={
                "event_type": "chat.member.invited",
                "recipient_ids": list(range(1, 502)),
            }
        )
        assert not s.is_valid()
        assert "recipient_ids" in s.errors
