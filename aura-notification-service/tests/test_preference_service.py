"""
Tests for PreferenceService business logic.

The `decide()` method is the core of the preference system — it determines
whether a notification should be delivered to a user on a given channel.
These tests exercise every decision branch without hitting the database.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from apps.notification.events.registry import EventDefinition
from apps.notification.models import NotificationPreference, PreferenceChannel
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

        decision = svc.decide(42, event, "inapp", prefs=prefs, overrides={}, now=NOW)

        assert decision.delivered is True
        assert decision.reason == "ok"

    def test_non_silenceable_event_delivered_even_when_channel_disabled(self):
        event = make_event(is_silenceable=False)
        prefs = make_prefs(inapp_enabled=False)

        decision = svc.decide(42, event, "inapp", prefs=prefs, overrides={}, now=NOW)

        assert decision.delivered is True

    def test_active_mute_suppresses_silenceable_event(self):
        event = make_event(is_silenceable=True)
        prefs = make_prefs(mute_until=FUTURE)

        decision = svc.decide(42, event, "inapp", prefs=prefs, overrides={}, now=NOW)

        assert decision.delivered is False
        assert decision.reason == "muted"

    def test_expired_mute_does_not_suppress(self):
        event = make_event(is_silenceable=True)
        prefs = make_prefs(mute_until=PAST)

        decision = svc.decide(42, event, "inapp", prefs=prefs, overrides={}, now=NOW)

        assert decision.delivered is True

    def test_mute_exactly_at_now_does_not_suppress(self):
        # Boundary: mute_until == now — condition is `now < mute_until`, so not suppressed
        event = make_event(is_silenceable=True)
        prefs = make_prefs(mute_until=NOW)

        decision = svc.decide(42, event, "inapp", prefs=prefs, overrides={}, now=NOW)

        assert decision.delivered is True

    def test_no_mute_set_does_not_suppress(self):
        event = make_event(is_silenceable=True)
        prefs = make_prefs(mute_until=None)

        decision = svc.decide(42, event, "inapp", prefs=prefs, overrides={}, now=NOW)

        assert decision.delivered is True

    def test_inapp_channel_globally_disabled_suppresses(self):
        event = make_event(is_silenceable=True, default_channels=("inapp",))
        prefs = make_prefs(inapp_enabled=False)

        decision = svc.decide(42, event, "inapp", prefs=prefs, overrides={}, now=NOW)

        assert decision.delivered is False
        assert decision.reason == "channel_disabled"

    def test_email_channel_globally_disabled_suppresses(self):
        event = make_event(is_silenceable=True, default_channels=("inapp", "email"))
        prefs = make_prefs(email_enabled=False)

        decision = svc.decide(42, event, "email", prefs=prefs, overrides={}, now=NOW)

        assert decision.delivered is False
        assert decision.reason == "channel_disabled"

    def test_inapp_disabled_does_not_affect_email_channel(self):
        event = make_event(is_silenceable=True, default_channels=("inapp", "email"))
        prefs = make_prefs(inapp_enabled=False, email_enabled=True)

        decision = svc.decide(42, event, "email", prefs=prefs, overrides={}, now=NOW)

        assert decision.delivered is True

    def test_event_override_enables_non_default_channel(self):
        # Email is not in default_channels, but user explicitly enabled it
        event = make_event(is_silenceable=True, default_channels=("inapp",))
        prefs = make_prefs(email_enabled=True)
        overrides = {("chat.member.invited", "email"): True}

        decision = svc.decide(42, event, "email", prefs=prefs, overrides=overrides, now=NOW)

        assert decision.delivered is True
        assert decision.reason == "ok"

    def test_event_override_disables_default_channel(self):
        # Inapp is in default_channels, but user explicitly disabled it
        event = make_event(is_silenceable=True, default_channels=("inapp",))
        prefs = make_prefs(inapp_enabled=True)
        overrides = {("chat.member.invited", "inapp"): False}

        decision = svc.decide(42, event, "inapp", prefs=prefs, overrides=overrides, now=NOW)

        assert decision.delivered is False
        assert decision.reason == "event_disabled"

    def test_no_override_and_channel_in_defaults_delivers(self):
        event = make_event(is_silenceable=True, default_channels=("inapp",))
        prefs = make_prefs(inapp_enabled=True)

        decision = svc.decide(42, event, "inapp", prefs=prefs, overrides={}, now=NOW)

        assert decision.delivered is True
        assert decision.reason == "ok"

    def test_no_override_and_channel_not_in_defaults_suppresses(self):
        event = make_event(is_silenceable=True, default_channels=("inapp",))
        prefs = make_prefs(email_enabled=True)

        decision = svc.decide(42, event, "email", prefs=prefs, overrides={}, now=NOW)

        assert decision.delivered is False
        assert decision.reason == "event_disabled"

    def test_override_for_different_event_does_not_affect_this_event(self):
        event = make_event(event_type="chat.member.invited", default_channels=("inapp",))
        prefs = make_prefs(inapp_enabled=True)
        # Override for a different event
        overrides = {("auth.new_login", "inapp"): False}

        decision = svc.decide(42, event, "inapp", prefs=prefs, overrides=overrides, now=NOW)

        assert decision.delivered is True


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
        assert result.inapp_enabled is True  # Django model default
        assert result.email_enabled is True
        assert result.mute_until is None


class TestPreferenceEventCatalogue:
    def test_catalogue_includes_all_registered_events(self):
        from apps.notification.events import iter_events
        expected_count = sum(1 for _ in iter_events())

        with patch.object(svc, "event_override_map", return_value={}):
            catalogue = svc.event_catalogue_for(42)

        assert len(catalogue) == expected_count

    def test_channels_reflect_user_override(self):
        overrides = {("chat.member.invited", "email"): True}

        with patch.object(svc, "event_override_map", return_value=overrides):
            catalogue = svc.event_catalogue_for(42)

        chat_invite = next(e for e in catalogue if e["event_type"] == "chat.member.invited")
        # User enabled email even though it's not a default channel
        assert chat_invite["channels"]["email"] is True

    def test_channels_reflect_default_when_no_override(self):
        with patch.object(svc, "event_override_map", return_value={}):
            catalogue = svc.event_catalogue_for(42)

        chat_invite = next(e for e in catalogue if e["event_type"] == "chat.member.invited")
        # Default: inapp=True, email=False (not in default_channels)
        assert chat_invite["channels"]["inapp"] is True
        assert chat_invite["channels"]["email"] is False

    def test_each_entry_has_channels_key(self):
        with patch.object(svc, "event_override_map", return_value={}):
            catalogue = svc.event_catalogue_for(42)

        for entry in catalogue:
            assert "channels" in entry, f"Missing 'channels' in {entry.get('event_type')}"
