import pytest
from unittest.mock import patch, MagicMock
from django.template import TemplateDoesNotExist

from apps.notification.events.registry import EventDefinition
from apps.notification.services.template_service import TemplateService, RenderedInApp, RenderedEmail

_RENDER = "apps.notification.services.template_service.render_to_string"


def make_event(
    event_type="chat.member.invited",
    description="Te invitaron a un chat.",
    template_id="chat_member_invited",
):
    def link_builder(ctx):
        return ctx.get("link_url")

    return EventDefinition(
        event_type=event_type,
        type="event",
        severity="info",
        description=description,
        default_channels=("inapp",),
        template_id=template_id,
        link_builder=link_builder,
    )


svc = TemplateService()


class TestRenderInapp:
    def test_renders_message_from_template(self):
        event = make_event()
        with patch(_RENDER, return_value="Rendered message"):
            result = svc.render_inapp(event, {})
        assert result.message == "Rendered message"

    def test_falls_back_to_description_when_template_missing(self):
        event = make_event(description="Fallback description")
        with patch(_RENDER, side_effect=TemplateDoesNotExist("missing")):
            result = svc.render_inapp(event, {})
        assert result.message == "Fallback description"

    def test_truncates_at_500_chars(self):
        event = make_event()
        long_text = "x" * 600
        with patch(_RENDER, return_value=long_text):
            result = svc.render_inapp(event, {})
        assert len(result.message) == 500
        assert result.message.endswith("...")

    def test_context_link_url_overrides_link_builder(self):
        event = make_event()
        with patch(_RENDER, return_value="msg"):
            result = svc.render_inapp(event, {"link_url": "http://custom.url"})
        assert result.link_url == "http://custom.url"

    def test_strips_whitespace_from_rendered_message(self):
        event = make_event()
        with patch(_RENDER, return_value="  trimmed  "):
            result = svc.render_inapp(event, {})
        assert result.message == "trimmed"

    def test_empty_render_falls_back_to_description(self):
        event = make_event(description="Default desc")
        with patch(_RENDER, return_value="   "):
            result = svc.render_inapp(event, {})
        assert result.message == "Default desc"

    def test_returns_rendered_inapp_dataclass(self):
        event = make_event()
        with patch(_RENDER, return_value="msg"):
            result = svc.render_inapp(event, {})
        assert isinstance(result, RenderedInApp)


class TestRenderEmail:
    def _side_effects(self, subject="Subject", text="Body", html=None):
        def side_effect(template, ctx):
            if "email_subject" in template:
                return subject
            if template.endswith(".txt"):
                return text
            if template.endswith(".html"):
                if html is None:
                    raise TemplateDoesNotExist(template)
                return html
            return ""
        return side_effect

    def test_renders_subject(self):
        event = make_event()
        with patch(_RENDER, side_effect=self._side_effects(subject="Test Subject")):
            result = svc.render_email(event, {})
        assert result.subject == "Test Subject"

    def test_renders_text_body(self):
        event = make_event()
        with patch(_RENDER, side_effect=self._side_effects(text="Text body")):
            result = svc.render_email(event, {})
        assert result.text_body == "Text body"

    def test_renders_html_body_when_exists(self):
        event = make_event()
        with patch(_RENDER, side_effect=self._side_effects(html="<b>HTML</b>")):
            result = svc.render_email(event, {})
        assert result.html_body == "<b>HTML</b>"

    def test_html_body_is_none_when_missing(self):
        event = make_event()
        with patch(_RENDER, side_effect=self._side_effects(html=None)):
            result = svc.render_email(event, {})
        assert result.html_body is None

    def test_fallback_subject_to_description(self):
        event = make_event(description="Fallback subject")
        def side_effect(template, ctx):
            raise TemplateDoesNotExist(template)
        with patch(_RENDER, side_effect=side_effect):
            result = svc.render_email(event, {})
        assert result.subject == "Fallback subject"

    def test_fallback_text_body_to_description(self):
        event = make_event(description="Fallback body")
        def side_effect(template, ctx):
            raise TemplateDoesNotExist(template)
        with patch(_RENDER, side_effect=side_effect):
            result = svc.render_email(event, {})
        assert result.text_body == "Fallback body"

    def test_returns_rendered_email_dataclass(self):
        event = make_event()
        with patch(_RENDER, side_effect=self._side_effects()):
            result = svc.render_email(event, {})
        assert isinstance(result, RenderedEmail)
