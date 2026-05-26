from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Optional
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string

from apps.notification.events import EventDefinition

logger = logging.getLogger(__name__)


@dataclass
class RenderedInApp:
    message: str
    link_url: Optional[str]


@dataclass
class RenderedEmail:
    subject: str
    text_body: str
    html_body: Optional[str]


class TemplateService:
    BASE_PATH = "notifications"

    def render_inapp(self, event: EventDefinition, context: dict) -> RenderedInApp:
        message = self._render(
            f"{self.BASE_PATH}/{event.template_id}/inapp.txt",
            context,
            fallback=event.description,
        ).strip()
        if not message:
            message = event.description
        if len(message) > 500:
            message = message[:497] + "..."
        try:
            link_url = event.link_builder(context) if event.link_builder else None
        except Exception:
            logger.exception("link_builder failed for %s", event.event_type)
            link_url = None
        return RenderedInApp(
            message=message,
            link_url=context.get("link_url") or link_url,
        )

    def render_email(self, event: EventDefinition, context: dict) -> RenderedEmail:
        subject = self._render(
            f"{self.BASE_PATH}/{event.template_id}/email_subject.txt",
            context,
            fallback=event.description,
        ).strip()
        text_body = self._render(
            f"{self.BASE_PATH}/{event.template_id}/email.txt",
            context,
            fallback=event.description,
        ).strip()
        html_body: Optional[str]
        try:
            html_body = render_to_string(
                f"{self.BASE_PATH}/{event.template_id}/email.html",
                context,
            )
        except TemplateDoesNotExist:
            html_body = None
        return RenderedEmail(subject=subject, text_body=text_body, html_body=html_body)

    @staticmethod
    def _render(path: str, context: dict, *, fallback: str) -> str:
        try:
            return render_to_string(path, context)
        except TemplateDoesNotExist:
            logger.warning("Template '%s' not found, using fallback string.", path)
            return fallback
        except Exception:
            logger.exception("Template '%s' failed to render.", path)
            return fallback


template_service = TemplateService()
