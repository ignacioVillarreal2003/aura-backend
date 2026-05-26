from __future__ import annotations
import logging
import smtplib
import requests
from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from apps.notification.events import get_event
from apps.notification.models import DispatchStatus, NotificationDispatch
from apps.notification.services.auth_lookup import lookup_recipient
from apps.notification.services.template_service import template_service

logger = logging.getLogger(__name__)

_RETRYABLE_EXCEPTIONS = (OSError, smtplib.SMTPException, requests.RequestException)


@shared_task(
    name="apps.notification.tasks.send_email_dispatch",
    bind=True,
    autoretry_for=_RETRYABLE_EXCEPTIONS,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
    acks_late=True,
)
def send_email_dispatch(
    self,
    *,
    dispatch_id: int,
    event_type: str,
    receiver_id: int,
    context: dict,
):
    dispatch = NotificationDispatch.objects.filter(pk=dispatch_id).first()
    if dispatch is None:
        logger.error("Dispatch row %s vanished before send.", dispatch_id)
        return "missing_dispatch_row"

    if dispatch.status in (DispatchStatus.SENT, DispatchStatus.FAILED):
        return f"already_{dispatch.status}"

    NotificationDispatch.objects.filter(pk=dispatch_id).update(
        attempt=(dispatch.attempt or 0) + 1,
    )

    recipient_email = (context or {}).get("recipient_email")
    recipient_name = (context or {}).get("recipient_name")
    if not recipient_email:
        looked = lookup_recipient(receiver_id) or {}
        recipient_email = looked.get("email")
        if not recipient_name:
            recipient_name = looked.get("username")

    if not recipient_email:
        _mark_failed(dispatch_id, "missing_recipient_email")
        return "missing_recipient_email"

    event = get_event(event_type)
    enriched_context = {**(context or {}), "recipient_name": recipient_name}
    rendered = template_service.render_email(event, enriched_context)

    try:
        message = EmailMultiAlternatives(
            subject=rendered.subject,
            body=rendered.text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email],
        )
        if rendered.html_body:
            message.attach_alternative(rendered.html_body, "text/html")
        message.send(fail_silently=False)
    except _RETRYABLE_EXCEPTIONS as exc:
        is_last_attempt = self.request.retries >= self.max_retries
        logger.warning(
            "Email send failed (dispatch=%s, attempt=%s, final=%s): %s",
            dispatch_id,
            self.request.retries,
            is_last_attempt,
            exc,
        )
        NotificationDispatch.objects.filter(pk=dispatch_id).update(
            status=DispatchStatus.FAILED if is_last_attempt else DispatchStatus.PENDING,
            error=str(exc)[:500] if is_last_attempt else None,
        )
        raise
    except Exception as exc:
        logger.warning(
            "Email send failed (non-retryable, dispatch=%s): %s",
            dispatch_id,
            exc,
        )
        NotificationDispatch.objects.filter(pk=dispatch_id).update(
            status=DispatchStatus.FAILED,
            error=str(exc)[:500],
        )
        raise

    NotificationDispatch.objects.filter(pk=dispatch_id).update(
        status=DispatchStatus.SENT,
        sent_at=timezone.now(),
        error=None,
    )
    return "sent"


def _mark_failed(dispatch_id: int, reason: str) -> None:
    NotificationDispatch.objects.filter(pk=dispatch_id).update(
        status=DispatchStatus.FAILED,
        error=reason,
    )
