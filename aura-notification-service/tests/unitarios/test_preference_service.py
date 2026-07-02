import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from apps.notification.events.registry import EventDefinition
from apps.notification.models import NotificationPreference
from apps.notification.services.preference_service import PreferenceService, PreferenceDecision

NOW = datetime(2024, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
FUTURE = datetime(2099, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
PAST = datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
NOW_EXACT = NOW


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

    def test_mute_at_exact_boundary_does_not_suppress(self):
        event = make_event(is_silenceable=True)
        prefs = make_prefs(mute_until=NOW)

        decision = svc.decide(42, event, "inapp", prefs=prefs, now=NOW)

        assert decision.delivered is True

    def test_decide_uses_db_prefs_when_not_passed(self):
        event = make_event(is_silenceable=True)
        default_prefs = make_prefs(inapp_enabled=True)

        with patch.object(svc, "get_global", return_value=default_prefs) as mock_get:
            decision = svc.decide(42, event, "inapp", prefs=None, now=NOW)

        mock_get.assert_called_once_with(42)
        assert decision.delivered is True

    def test_inapp_and_email_both_disabled_suppresses_both(self):
        event = make_event(is_silenceable=True, default_channels=("inapp", "email"))
        prefs = make_prefs(inapp_enabled=False, email_enabled=False)

        inapp_decision = svc.decide(42, event, "inapp", prefs=prefs, now=NOW)
        email_decision = svc.decide(42, event, "email", prefs=prefs, now=NOW)

        assert inapp_decision.delivered is False
        assert email_decision.delivered is False

    def test_non_silenceable_ignores_all_global_flags(self):
        event = make_event(is_silenceable=False, default_channels=("inapp", "email"))
        prefs = make_prefs(inapp_enabled=False, email_enabled=False, mute_until=FUTURE)

        inapp_decision = svc.decide(42, event, "inapp", prefs=prefs, now=NOW)
        email_decision = svc.decide(42, event, "email", prefs=prefs, now=NOW)

        assert inapp_decision.delivered is True
        assert email_decision.delivered is True


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


class TestPreferenceGetGlobalMap:
    def test_returns_map_keyed_by_user_id(self):
        p1 = NotificationPreference(user_id=1)
        p2 = NotificationPreference(user_id=2)
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([p1, p2]))

        with patch.object(NotificationPreference.objects, "filter", return_value=mock_qs):
            result = svc.get_global_map([1, 2])

        assert result[1] is p1
        assert result[2] is p2

    def test_fills_missing_users_with_defaults(self):
        p1 = NotificationPreference(user_id=1)
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([p1]))

        with patch.object(NotificationPreference.objects, "filter", return_value=mock_qs):
            result = svc.get_global_map([1, 2])

        assert result[1] is p1
        assert result[2].user_id == 2
        assert result[2].inapp_enabled is True

    def test_empty_user_list_returns_empty_map(self):
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([]))

        with patch.object(NotificationPreference.objects, "filter", return_value=mock_qs):
            result = svc.get_global_map([])

        assert result == {}


class TestPreferenceUpsertGlobal:
    def test_upsert_creates_row_when_not_exists(self):
        new_prefs = NotificationPreference(user_id=10)
        with patch.object(
            NotificationPreference.objects, "get_or_create",
            return_value=(new_prefs, True),
        ):
            with patch.object(new_prefs, "save"):
                result = svc.upsert_global(10, inapp_enabled=False)

        assert result.inapp_enabled is False

    def test_upsert_updates_inapp_enabled(self):
        existing = NotificationPreference(user_id=10)
        existing.inapp_enabled = True
        with patch.object(
            NotificationPreference.objects, "get_or_create",
            return_value=(existing, False),
        ):
            with patch.object(existing, "save"):
                result = svc.upsert_global(10, inapp_enabled=False)

        assert result.inapp_enabled is False

    def test_clear_mute_sets_mute_until_to_none(self):
        from datetime import datetime, timezone
        existing = NotificationPreference(user_id=10)
        existing.mute_until = datetime(2099, 1, 1, tzinfo=timezone.utc)
        with patch.object(
            NotificationPreference.objects, "get_or_create",
            return_value=(existing, False),
        ):
            with patch.object(existing, "save"):
                result = svc.upsert_global(10, clear_mute=True)

        assert result.mute_until is None
