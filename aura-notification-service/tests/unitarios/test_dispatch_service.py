import pytest
from unittest.mock import patch, MagicMock, ANY

from apps.notification.services.dispatch_service import DispatchOutcome, DispatchService
from apps.notification.events.registry import EventDefinition
from apps.notification.models import PreferenceChannel, EmailDispatchStatus, NotificationPreference
from apps.notification.services.preference_service import PreferenceDecision

_PREF_SVC = "apps.notification.services.dispatch_service.preference_service"
_TEMPLATE_SVC = "apps.notification.services.dispatch_service.template_service"
_REALTIME_SVC = "apps.notification.services.dispatch_service.realtime_service"
_GET_EVENT = "apps.notification.services.dispatch_service.get_event"
_EMAIL_DISPATCH = "apps.notification.services.dispatch_service.EmailDispatch.objects"
_NOTIFICATION = "apps.notification.services.dispatch_service.Notification"


def make_event(
    event_type="chat.member.invited",
    default_channels=(PreferenceChannel.INAPP,),
    is_silenceable=True,
):
    def link_builder(ctx):
        return None

    return EventDefinition(
        event_type=event_type,
        type="event",
        severity="info",
        description="Test event.",
        default_channels=default_channels,
        template_id="test_template",
        is_silenceable=is_silenceable,
        available_channels=(PreferenceChannel.INAPP, PreferenceChannel.EMAIL),
        link_builder=link_builder,
    )


def make_prefs(user_id=1):
    p = NotificationPreference(user_id=user_id)
    p.inapp_enabled = True
    p.email_enabled = True
    p.mute_until = None
    return p


def make_rendered_inapp():
    from apps.notification.services.template_service import RenderedInApp
    return RenderedInApp(message="Rendered message", link_url=None)


svc = DispatchService()


class TestDispatchOutcome:
    def test_to_dict_includes_receiver_id(self):
        outcome = DispatchOutcome(receiver_id=5, notification_id=10)
        d = outcome.to_dict()
        assert d["receiver_id"] == 5

    def test_to_dict_includes_notification_id(self):
        outcome = DispatchOutcome(receiver_id=5, notification_id=10)
        d = outcome.to_dict()
        assert d["notification_id"] == 10

    def test_to_dict_includes_channels_map(self):
        outcome = DispatchOutcome(receiver_id=5, notification_id=10, channels={"inapp": "sent"})
        d = outcome.to_dict()
        assert d["channels"] == {"inapp": "sent"}

    def test_channels_default_empty_dict(self):
        outcome = DispatchOutcome(receiver_id=1, notification_id=None)
        assert outcome.channels == {}


class TestDispatchEvent:
    def _base_mocks(self, event, decisions=None):
        if decisions is None:
            decisions = {
                PreferenceChannel.INAPP: PreferenceDecision(delivered=True, reason="ok")
            }
        prefs = make_prefs()
        pref_map = {1: prefs, 2: prefs}
        return event, prefs, pref_map, decisions

    def test_returns_one_outcome_per_recipient(self):
        event = make_event()
        with (
            patch(_GET_EVENT, return_value=event),
            patch(_PREF_SVC) as pref_svc,
            patch(_TEMPLATE_SVC) as tmpl_svc,
            patch(_REALTIME_SVC),
            patch.object(svc, "_create_notification_row") as mock_create,
        ):
            prefs = make_prefs()
            pref_svc.get_global_map.return_value = {1: prefs, 2: prefs}
            pref_svc.decide.return_value = PreferenceDecision(delivered=False, reason="channel_disabled")
            outcomes = svc.dispatch_event(
                event_type=event.event_type,
                recipient_ids=[1, 2],
                actor_id=None,
                actor_name=None,
                context={},
            )
        assert len(outcomes) == 2

    def test_outcome_has_receiver_id(self):
        event = make_event()
        with (
            patch(_GET_EVENT, return_value=event),
            patch(_PREF_SVC) as pref_svc,
            patch(_TEMPLATE_SVC),
            patch(_REALTIME_SVC),
        ):
            pref_svc.get_global_map.return_value = {42: make_prefs(42)}
            pref_svc.decide.return_value = PreferenceDecision(delivered=False, reason="muted")
            outcomes = svc.dispatch_event(
                event_type=event.event_type,
                recipient_ids=[42],
                actor_id=None,
                actor_name=None,
            )
        assert outcomes[0].receiver_id == 42

    def test_prefetches_prefs_for_all_recipients(self):
        event = make_event()
        with (
            patch(_GET_EVENT, return_value=event),
            patch(_PREF_SVC) as pref_svc,
            patch(_TEMPLATE_SVC),
            patch(_REALTIME_SVC),
        ):
            pref_svc.get_global_map.return_value = {}
            pref_svc.decide.return_value = PreferenceDecision(delivered=False, reason="muted")
            svc.dispatch_event(
                event_type=event.event_type,
                recipient_ids=[1, 2, 3],
                actor_id=None,
                actor_name=None,
            )
        pref_svc.get_global_map.assert_called_once_with([1, 2, 3])

    def test_forwards_actor_name_to_context(self):
        event = make_event()
        with (
            patch(_GET_EVENT, return_value=event),
            patch(_PREF_SVC) as pref_svc,
            patch(_TEMPLATE_SVC) as tmpl_svc,
            patch(_REALTIME_SVC),
            patch.object(svc, "_create_notification_row") as mock_create,
        ):
            prefs = make_prefs()
            pref_svc.get_global_map.return_value = {1: prefs}
            pref_svc.decide.return_value = PreferenceDecision(delivered=True, reason="ok")
            tmpl_svc.render_inapp.return_value = make_rendered_inapp()
            mock_create.return_value = MagicMock(id=1, receiver_id=1, created_at=None)
            svc.dispatch_event(
                event_type=event.event_type,
                recipient_ids=[1],
                actor_id=None,
                actor_name="Alice",
                context={},
            )
        call_kwargs = tmpl_svc.render_inapp.call_args[0][1]
        assert call_kwargs.get("actor_name") == "Alice"

    def test_empty_context_defaults_to_empty_dict(self):
        event = make_event()
        with (
            patch(_GET_EVENT, return_value=event),
            patch(_PREF_SVC) as pref_svc,
            patch(_TEMPLATE_SVC),
            patch(_REALTIME_SVC),
        ):
            pref_svc.get_global_map.return_value = {}
            pref_svc.decide.return_value = PreferenceDecision(delivered=False, reason="muted")
            outcomes = svc.dispatch_event(
                event_type=event.event_type,
                recipient_ids=[1],
                actor_id=None,
                actor_name=None,
                context=None,
            )
        assert len(outcomes) == 1


class TestInappChannel:
    def test_creates_notification_when_inapp_delivered(self):
        event = make_event(default_channels=(PreferenceChannel.INAPP,))
        with (
            patch(_PREF_SVC) as pref_svc,
            patch(_TEMPLATE_SVC) as tmpl_svc,
            patch(_REALTIME_SVC),
            patch.object(svc, "_create_notification_row") as mock_create,
        ):
            prefs = make_prefs()
            pref_svc.get_global.return_value = prefs
            pref_svc.decide.return_value = PreferenceDecision(delivered=True, reason="ok")
            tmpl_svc.render_inapp.return_value = make_rendered_inapp()
            mock_create.return_value = MagicMock(id=99, receiver_id=1, created_at=None)
            svc._dispatch_one(
                event=event, receiver_id=1, actor_id=None, actor_name=None,
                context={}, link_url=None, prefetched_prefs=prefs,
            )
        mock_create.assert_called_once()

    def test_skips_creation_when_inapp_suppressed(self):
        event = make_event(default_channels=(PreferenceChannel.INAPP,))
        with (
            patch(_PREF_SVC) as pref_svc,
            patch(_TEMPLATE_SVC),
            patch(_REALTIME_SVC),
            patch.object(svc, "_create_notification_row") as mock_create,
        ):
            pref_svc.decide.return_value = PreferenceDecision(delivered=False, reason="muted")
            svc._dispatch_one(
                event=event, receiver_id=1, actor_id=None, actor_name=None,
                context={}, link_url=None, prefetched_prefs=make_prefs(),
            )
        mock_create.assert_not_called()

    def test_outcome_inapp_sent_when_delivered(self):
        event = make_event(default_channels=(PreferenceChannel.INAPP,))
        with (
            patch(_PREF_SVC) as pref_svc,
            patch(_TEMPLATE_SVC) as tmpl_svc,
            patch(_REALTIME_SVC),
            patch.object(svc, "_create_notification_row") as mock_create,
        ):
            pref_svc.decide.return_value = PreferenceDecision(delivered=True, reason="ok")
            tmpl_svc.render_inapp.return_value = make_rendered_inapp()
            mock_create.return_value = MagicMock(id=1, receiver_id=1, created_at=None)
            outcome = svc._dispatch_one(
                event=event, receiver_id=1, actor_id=None, actor_name=None,
                context={}, link_url=None, prefetched_prefs=make_prefs(),
            )
        assert outcome.channels[PreferenceChannel.INAPP] == EmailDispatchStatus.SENT

    def test_outcome_inapp_skipped_when_suppressed(self):
        event = make_event(default_channels=(PreferenceChannel.INAPP,))
        with (
            patch(_PREF_SVC) as pref_svc,
            patch(_TEMPLATE_SVC),
            patch(_REALTIME_SVC),
        ):
            pref_svc.decide.return_value = PreferenceDecision(delivered=False, reason="muted")
            outcome = svc._dispatch_one(
                event=event, receiver_id=1, actor_id=None, actor_name=None,
                context={}, link_url=None, prefetched_prefs=make_prefs(),
            )
        assert outcome.channels[PreferenceChannel.INAPP] == EmailDispatchStatus.SKIPPED

    def test_publishes_created_event_after_save(self):
        event = make_event(default_channels=(PreferenceChannel.INAPP,))
        with (
            patch(_PREF_SVC) as pref_svc,
            patch(_TEMPLATE_SVC) as tmpl_svc,
            patch(_REALTIME_SVC) as mock_rt,
            patch.object(svc, "_create_notification_row") as mock_create,
            patch.object(svc, "_publish_created") as mock_pub,
        ):
            pref_svc.decide.return_value = PreferenceDecision(delivered=True, reason="ok")
            tmpl_svc.render_inapp.return_value = make_rendered_inapp()
            mock_create.return_value = MagicMock(id=1, receiver_id=1, created_at=None)
            svc._dispatch_one(
                event=event, receiver_id=1, actor_id=None, actor_name=None,
                context={}, link_url=None, prefetched_prefs=make_prefs(),
            )
        mock_pub.assert_called_once()


class TestEmailChannel:
    def test_creates_email_dispatch_when_email_delivered(self):
        event = make_event(default_channels=(PreferenceChannel.EMAIL,))
        dispatch_mock = MagicMock()
        dispatch_mock.id = 1
        dispatch_mock.payload = {}
        with (
            patch(_PREF_SVC) as pref_svc,
            patch(_TEMPLATE_SVC),
            patch(_REALTIME_SVC),
            patch(_EMAIL_DISPATCH) as mock_ed,
            patch.object(svc, "_enqueue_email"),
        ):
            mock_ed.create.return_value = dispatch_mock
            pref_svc.decide.return_value = PreferenceDecision(delivered=True, reason="ok")
            svc._dispatch_one(
                event=event, receiver_id=1, actor_id=None, actor_name=None,
                context={}, link_url=None, prefetched_prefs=make_prefs(),
            )
        mock_ed.create.assert_called_once()

    def test_outcome_email_pending_when_delivered(self):
        event = make_event(default_channels=(PreferenceChannel.EMAIL,))
        dispatch_mock = MagicMock()
        dispatch_mock.id = 1
        dispatch_mock.payload = {}
        with (
            patch(_PREF_SVC) as pref_svc,
            patch(_TEMPLATE_SVC),
            patch(_REALTIME_SVC),
            patch(_EMAIL_DISPATCH) as mock_ed,
            patch.object(svc, "_enqueue_email"),
        ):
            mock_ed.create.return_value = dispatch_mock
            pref_svc.decide.return_value = PreferenceDecision(delivered=True, reason="ok")
            outcome = svc._dispatch_one(
                event=event, receiver_id=1, actor_id=None, actor_name=None,
                context={}, link_url=None, prefetched_prefs=make_prefs(),
            )
        assert outcome.channels[PreferenceChannel.EMAIL] == EmailDispatchStatus.PENDING

    def test_outcome_email_skipped_when_suppressed(self):
        event = make_event(default_channels=(PreferenceChannel.EMAIL,))
        with (
            patch(_PREF_SVC) as pref_svc,
            patch(_TEMPLATE_SVC),
            patch(_REALTIME_SVC),
            patch(_EMAIL_DISPATCH) as mock_ed,
        ):
            pref_svc.decide.return_value = PreferenceDecision(delivered=False, reason="muted")
            mock_ed.create.return_value = MagicMock()
            outcome = svc._dispatch_one(
                event=event, receiver_id=1, actor_id=None, actor_name=None,
                context={}, link_url=None, prefetched_prefs=make_prefs(),
            )
        assert outcome.channels[PreferenceChannel.EMAIL] == EmailDispatchStatus.SKIPPED

    def test_creates_skipped_dispatch_when_suppressed(self):
        event = make_event(default_channels=(PreferenceChannel.EMAIL,))
        with (
            patch(_PREF_SVC) as pref_svc,
            patch(_TEMPLATE_SVC),
            patch(_REALTIME_SVC),
            patch(_EMAIL_DISPATCH) as mock_ed,
        ):
            pref_svc.decide.return_value = PreferenceDecision(delivered=False, reason="muted")
            mock_ed.create.return_value = MagicMock()
            svc._dispatch_one(
                event=event, receiver_id=1, actor_id=None, actor_name=None,
                context={}, link_url=None, prefetched_prefs=make_prefs(),
            )
        mock_ed.create.assert_called_once()
        call_kwargs = mock_ed.create.call_args[1]
        assert call_kwargs["status"] == EmailDispatchStatus.SKIPPED

    def test_enqueues_celery_task_when_email_delivered(self):
        event = make_event(default_channels=(PreferenceChannel.EMAIL,))
        dispatch_mock = MagicMock()
        dispatch_mock.id = 5
        dispatch_mock.payload = {}
        with (
            patch(_PREF_SVC) as pref_svc,
            patch(_TEMPLATE_SVC),
            patch(_REALTIME_SVC),
            patch(_EMAIL_DISPATCH) as mock_ed,
            patch.object(svc, "_enqueue_email") as mock_enqueue,
        ):
            mock_ed.create.return_value = dispatch_mock
            pref_svc.decide.return_value = PreferenceDecision(delivered=True, reason="ok")
            svc._dispatch_one(
                event=event, receiver_id=1, actor_id=None, actor_name=None,
                context={}, link_url=None, prefetched_prefs=make_prefs(),
            )
        mock_enqueue.assert_called_once()
