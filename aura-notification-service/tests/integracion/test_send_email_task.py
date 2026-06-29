"""
Tests de integración para la tarea Celery send_email_dispatch.
Usa CELERY_TASK_ALWAYS_EAGER=True y backend de email en memoria.
"""
import pytest
from unittest.mock import patch, MagicMock
from django.core import mail

from apps.notification.models.dispatch import EmailDispatch, EmailDispatchStatus
from apps.notification.tasks.send_email import send_email_dispatch
from apps.notification.services.template_service import RenderedEmail

pytestmark = pytest.mark.django_db


def _make_dispatch(receiver_id=42, event_type="chat.member.invited", status=EmailDispatchStatus.PENDING):
    return EmailDispatch.objects.create(
        receiver_id=receiver_id,
        event_type=event_type,
        status=status,
        payload={"recipient_email": "user@test.com"},
    )


def _rendered_email(subject="Subj", text="Body", html=None):
    return RenderedEmail(subject=subject, text_body=text, html_body=html)


_TEMPLATE_SVC = "apps.notification.tasks.send_email.template_service"
_LOOKUP = "apps.notification.tasks.send_email.lookup_recipient"


class TestSendEmailDispatchTask:
    def test_missing_dispatch_row_exits_early(self):
        result = send_email_dispatch(
            dispatch_id=99999,
            event_type="chat.member.invited",
            receiver_id=42,
            context={},
        )
        assert result == "missing_dispatch_row"

    def test_already_sent_exits_early(self):
        dispatch = _make_dispatch(status=EmailDispatchStatus.SENT)
        with patch(_TEMPLATE_SVC):
            result = send_email_dispatch(
                dispatch_id=dispatch.id,
                event_type=dispatch.event_type,
                receiver_id=dispatch.receiver_id,
                context=dispatch.payload,
            )
        assert result == "already_sent"

    def test_already_failed_exits_early(self):
        dispatch = _make_dispatch(status=EmailDispatchStatus.FAILED)
        with patch(_TEMPLATE_SVC):
            result = send_email_dispatch(
                dispatch_id=dispatch.id,
                event_type=dispatch.event_type,
                receiver_id=dispatch.receiver_id,
                context=dispatch.payload,
            )
        assert result == "already_failed"

    def test_sends_email_when_email_in_context(self):
        dispatch = _make_dispatch()
        with patch(_TEMPLATE_SVC) as svc:
            svc.render_email.return_value = _rendered_email()
            result = send_email_dispatch(
                dispatch_id=dispatch.id,
                event_type=dispatch.event_type,
                receiver_id=dispatch.receiver_id,
                context={"recipient_email": "user@test.com"},
            )
        assert result == "sent"

    def test_marks_dispatch_sent(self):
        dispatch = _make_dispatch()
        with patch(_TEMPLATE_SVC) as svc:
            svc.render_email.return_value = _rendered_email()
            send_email_dispatch(
                dispatch_id=dispatch.id,
                event_type=dispatch.event_type,
                receiver_id=dispatch.receiver_id,
                context={"recipient_email": "user@test.com"},
            )
        dispatch.refresh_from_db()
        assert dispatch.status == EmailDispatchStatus.SENT

    def test_sets_sent_at(self):
        dispatch = _make_dispatch()
        with patch(_TEMPLATE_SVC) as svc:
            svc.render_email.return_value = _rendered_email()
            send_email_dispatch(
                dispatch_id=dispatch.id,
                event_type=dispatch.event_type,
                receiver_id=dispatch.receiver_id,
                context={"recipient_email": "user@test.com"},
            )
        dispatch.refresh_from_db()
        assert dispatch.sent_at is not None

    def test_no_email_in_context_uses_auth_lookup(self):
        dispatch = _make_dispatch()
        dispatch.payload = {}
        dispatch.save()
        with (
            patch(_LOOKUP, return_value={"email": "found@test.com", "username": "user"}),
            patch(_TEMPLATE_SVC) as svc,
        ):
            svc.render_email.return_value = _rendered_email()
            result = send_email_dispatch(
                dispatch_id=dispatch.id,
                event_type=dispatch.event_type,
                receiver_id=dispatch.receiver_id,
                context={},
            )
        assert result == "sent"

    def test_marks_failed_when_no_recipient_email(self):
        dispatch = _make_dispatch()
        dispatch.payload = {}
        dispatch.save()
        with patch(_LOOKUP, return_value=None):
            result = send_email_dispatch(
                dispatch_id=dispatch.id,
                event_type=dispatch.event_type,
                receiver_id=dispatch.receiver_id,
                context={},
            )
        assert result == "missing_recipient_email"
        dispatch.refresh_from_db()
        assert dispatch.status == EmailDispatchStatus.FAILED

    def test_auth_lookup_returns_none_marks_failed(self):
        dispatch = _make_dispatch()
        dispatch.payload = {}
        dispatch.save()
        with patch(_LOOKUP, return_value={}):
            result = send_email_dispatch(
                dispatch_id=dispatch.id,
                event_type=dispatch.event_type,
                receiver_id=dispatch.receiver_id,
                context={},
            )
        assert result == "missing_recipient_email"

    def test_increments_attempt_counter(self):
        dispatch = _make_dispatch()
        initial_attempt = dispatch.attempt or 0
        with patch(_TEMPLATE_SVC) as svc:
            svc.render_email.return_value = _rendered_email()
            send_email_dispatch(
                dispatch_id=dispatch.id,
                event_type=dispatch.event_type,
                receiver_id=dispatch.receiver_id,
                context={"recipient_email": "user@test.com"},
            )
        dispatch.refresh_from_db()
        assert dispatch.attempt == initial_attempt + 1

    def test_attaches_html_when_html_body_present(self):
        dispatch = _make_dispatch()
        with patch(_TEMPLATE_SVC) as svc:
            svc.render_email.return_value = _rendered_email(html="<b>HTML</b>")
            send_email_dispatch(
                dispatch_id=dispatch.id,
                event_type=dispatch.event_type,
                receiver_id=dispatch.receiver_id,
                context={"recipient_email": "user@test.com"},
            )
        assert len(mail.outbox) >= 1
        msg = mail.outbox[-1]
        assert any("text/html" in str(alt) for alt in msg.alternatives)

    def test_no_html_when_html_body_none(self):
        dispatch = _make_dispatch()
        with patch(_TEMPLATE_SVC) as svc:
            svc.render_email.return_value = _rendered_email(html=None)
            send_email_dispatch(
                dispatch_id=dispatch.id,
                event_type=dispatch.event_type,
                receiver_id=dispatch.receiver_id,
                context={"recipient_email": "user@test.com"},
            )
        msg = mail.outbox[-1]
        assert not msg.alternatives

    def test_email_in_outbox_after_successful_send(self):
        dispatch = _make_dispatch()
        before = len(mail.outbox)
        with patch(_TEMPLATE_SVC) as svc:
            svc.render_email.return_value = _rendered_email(subject="Test Subject")
            send_email_dispatch(
                dispatch_id=dispatch.id,
                event_type=dispatch.event_type,
                receiver_id=dispatch.receiver_id,
                context={"recipient_email": "user@test.com"},
            )
        assert len(mail.outbox) == before + 1
        assert mail.outbox[-1].subject == "Test Subject"
