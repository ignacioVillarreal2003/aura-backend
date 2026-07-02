import pytest

from apps.notification.events.registry import (
    EventDefinition,
    EventType,
    get_event,
    is_known_event,
    iter_events,
    _chat_link,
    _document_link,
)
from apps.notification.models import NotificationSeverity, PreferenceChannel


class TestEventRegistry:
    def test_get_event_returns_definition_for_known_type(self):
        event = get_event(EventType.CHAT_MEMBER_INVITED)
        assert event.event_type == EventType.CHAT_MEMBER_INVITED

    def test_get_event_raises_for_unknown_type(self):
        with pytest.raises(KeyError):
            get_event("unknown.event.type")

    def test_is_known_true_for_registered(self):
        assert is_known_event(EventType.CHAT_MEMBER_INVITED) is True

    def test_is_known_false_for_unknown(self):
        assert is_known_event("no.such.event") is False

    def test_iter_events_yields_nine_events(self):
        events = list(iter_events())
        assert len(events) == 9

    def test_all_events_have_template_id(self):
        for event in iter_events():
            assert event.template_id, f"{event.event_type} has no template_id"

    def test_non_silenceable_are_password_changed_and_announcement(self):
        non_silenceable = [e for e in iter_events() if not e.is_silenceable]
        types = {e.event_type for e in non_silenceable}
        assert EventType.AUTH_PASSWORD_CHANGED in types
        assert EventType.SYSTEM_ANNOUNCEMENT in types

    def test_all_events_have_inapp_in_available_channels(self):
        for event in iter_events():
            assert PreferenceChannel.INAPP in event.available_channels, (
                f"{event.event_type} missing inapp in available_channels"
            )


class TestEventDefinition:
    def test_has_channel_true_when_in_defaults(self):
        event = get_event(EventType.CHAT_MEMBER_INVITED)
        assert event.has_channel(PreferenceChannel.INAPP) is True

    def test_has_channel_false_when_not_in_defaults(self):
        event = get_event(EventType.CHAT_MEMBER_INVITED)
        assert event.has_channel(PreferenceChannel.EMAIL) is False

    def test_to_public_dict_excludes_link_builder(self):
        event = get_event(EventType.CHAT_MEMBER_INVITED)
        d = event.to_public_dict()
        assert "link_builder" not in d

    def test_to_public_dict_includes_required_keys(self):
        event = get_event(EventType.CHAT_MEMBER_INVITED)
        d = event.to_public_dict()
        required_keys = {
            "event_type", "type", "severity", "description",
            "default_channels", "available_channels", "is_silenceable",
        }
        assert required_keys.issubset(d.keys())

    def test_chat_link_builder_returns_url(self, settings):
        settings.NOTIFICATION_DEFAULT_LINK_BASE_URL = "http://example.com"
        result = _chat_link({"chat_id": 5})
        assert result == "http://example.com/chats/5"

    def test_chat_link_builder_returns_none_without_chat_id(self, settings):
        settings.NOTIFICATION_DEFAULT_LINK_BASE_URL = "http://example.com"
        result = _chat_link({})
        assert result is None

    def test_document_link_builder_returns_url(self, settings):
        settings.NOTIFICATION_DEFAULT_LINK_BASE_URL = "http://example.com"
        result = _document_link({"document_id": 7})
        assert result == "http://example.com/documents/7"

    def test_document_link_builder_returns_none_without_document_id(self, settings):
        settings.NOTIFICATION_DEFAULT_LINK_BASE_URL = "http://example.com"
        result = _document_link({})
        assert result is None
