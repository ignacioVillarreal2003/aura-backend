"""
Tests for PreferenceService business logic.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from apps.notification.events.registry import EventDefinition
from apps.notification.models import NotificationPreference
from apps.notification.services.preference_service import PreferenceService, PreferenceDecision

NOW = datetime(2024, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
FUTURE = datetime(2099, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
PAST = datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def make_event(
    event_type="chat.member.invited",
    is_silenceable=True,
    default_channels=("inapp",),
    available_channels=("inapp", "email"),
):
    return EventDefinition(
        event_type=event_type,
        type="event",
        severity="info",
        description="Test event description.",
        default_channels=default_channels,
        template_id="test_template",
        is_silenceable=is_silenceable,
        available_channels=available_channels,
    )


def make_prefs(inapp_enabled=True, email_enabled=True, mute_until=None):
    p = NotificationPreference(user_id=42)
    p.inapp_enabled = inapp_enabled
    p.email_enabled = email_enabled
    p.mute_until = mute_until
    return p


svc = PreferenceService()


class TestPreferenceDecide:
    def test_non_silenceable_event_always_delivered_despite_active_mute(self):
        event = make_event(is_silenceable=False)
        prefs = make_prefs(mute_until=FUTURE)

        decision = svc.decide(42, event, "inapp", prefs=prefs, now=NOW)

        assert decision.delivered is True
        assert decision.reason == "ok"

    def test_non_silenceable_event_delivered_even_when_channel_disabled(self):
        event = make_event(is_silenceable=False)
        prefs = make_prefs(inapp_enabled=False)

        decision = svc.decide(42, event, "inapp", prefs=prefs, now=NOW)

        assert decision.delivered is True

    def test_active_mute_suppresses_silenceable_event(self):
        event = make_event(is_silenceable=True)
        prefs = make_prefs(mute_until=FUTURE)

        decision = svc.decide(42, event, "inapp", prefs=prefs, now=NOW)

        assert decision.delivered is False
        assert decision.reason == "muted"

    def test_expired_mute_does_not_suppress(self):
        event = make_event(is_silenceable=True)
        prefs = make_prefs(mute_until=PAST)

        decision = svc.decide(42, event, "inapp", prefs=prefs, now=NOW)

        assert decision.delivered is True

    def test_inapp_channel_globally_disabled_suppresses(self):
        event = make_event(is_silenceable=True, default_channels=("inapp",))
        prefs = make_prefs(inapp_enabled=False)

        decision = svc.decide(42, event, "inapp", prefs=prefs, now=NOW)

        assert decision.delivered is False
        assert decision.reason == "channel_disabled"

    def test_email_channel_globally_disabled_suppresses(self):
        event = make_event(is_silenceable=True, default_channels=("inapp", "email"))
        prefs = make_prefs(email_enabled=False)

        decision = svc.decide(42, event, "email", prefs=prefs, now=NOW)

        assert decision.delivered is False
        assert decision.reason == "channel_disabled"

    def test_channel_in_defaults_delivers(self):
        event = make_event(is_silenceable=True, default_channels=("inapp",))
        prefs = make_prefs(inapp_enabled=True)

        decision = svc.decide(42, event, "inapp", prefs=prefs, now=NOW)

        assert decision.delivered is True
        assert decision.reason == "ok"

    def test_channel_not_in_defaults_suppresses(self):
        event = make_event(is_silenceable=True, default_channels=("inapp",))
        prefs = make_prefs(email_enabled=True)

        decision = svc.decide(42, event, "email", prefs=prefs, now=NOW)

        assert decision.delivered is False
        assert decision.reason == "event_disabled"


class TestPreferenceGetGlobal:
    def test_returns_existing_preferences_from_db(self):
        existing = NotificationPreference(user_id=42)
        existing.inapp_enabled = False
        existing.email_enabled = True

        with patch.object(NotificationPreference.objects, "get", return_value=existing):
            result = svc.get_global(42)

        assert result.inapp_enabled is False
        assert result.email_enabled is True

    def test_returns_default_preferences_when_no_db_row(self):
        with patch.object(
            NotificationPreference.objects, "get",
            side_effect=NotificationPreference.DoesNotExist
        ):
            result = svc.get_global(42)

        assert result.user_id == 42
        assert result.inapp_enabled is True
        assert result.email_enabled is True
        assert result.mute_until is None
