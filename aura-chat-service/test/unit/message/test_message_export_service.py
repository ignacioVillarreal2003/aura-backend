"""
Unit tests for the message export service (chat PDF / Markdown / JSON rendering).

Previously untested: the view-layer tests mock the generate_* functions entirely.
These exercise the rendering helpers directly, including the dangerous-tag
sanitization used before rendering user content to PDF.
"""
import datetime
import json

import pytest

from apps.artifact_message.exceptions import PDFGenerationException
from apps.artifact_message.services.export_service import (
    _fmt_dt,
    _render_markdown,
    generate_chat_markdown,
    generate_chat_pdf,
    generate_message_pdf,
)
from test.conftest import make_chat, make_message

EXPORT = "apps.artifact_message.services.export_service"


def _conversation():
    """A small user/AI conversation."""
    return [
        make_message(msg_id=1, sender_type="user", message="¿Cuál es el plan?"),
        make_message(msg_id=2, sender_type="assistant", message="El plan es avanzar."),
        make_message(msg_id=3, sender_type="user", message="Entendido."),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# _fmt_dt
# ══════════════════════════════════════════════════════════════════════════════

def test_fmt_dt_none_returns_empty_string():
    assert _fmt_dt(None) == ""


def test_fmt_dt_formats_aware_datetime_as_utc():
    dt = datetime.datetime(2025, 3, 15, 9, 30, tzinfo=datetime.timezone.utc)
    assert _fmt_dt(dt) == "2025-03-15 09:30 UTC"


def test_fmt_dt_converts_other_timezone_to_utc():
    tz = datetime.timezone(datetime.timedelta(hours=3))
    dt = datetime.datetime(2025, 3, 15, 12, 30, tzinfo=tz)  # 09:30 UTC
    assert _fmt_dt(dt) == "2025-03-15 09:30 UTC"


# ══════════════════════════════════════════════════════════════════════════════
# _render_markdown — rendering + dangerous-tag sanitization
# ══════════════════════════════════════════════════════════════════════════════

def test_render_markdown_renders_headings_and_bold():
    html = _render_markdown("# Título\n\ntexto **negrita**")
    assert "<h1" in html
    assert "<strong>negrita</strong>" in html


def test_render_markdown_renders_tables():
    html = _render_markdown("| A | B |\n| - | - |\n| 1 | 2 |")
    assert "<table>" in html


def test_render_markdown_strips_script_tags():
    html = _render_markdown("Hola <script>alert('x')</script> mundo")
    assert "<script" not in html.lower()


def test_render_markdown_strips_iframe_and_form_tags():
    html = _render_markdown("<iframe src='evil'></iframe><form><input></form>")
    assert "<iframe" not in html.lower()
    assert "<form" not in html.lower()
    assert "<input" not in html.lower()


# ══════════════════════════════════════════════════════════════════════════════
# generate_chat_markdown
# ══════════════════════════════════════════════════════════════════════════════

def test_chat_markdown_includes_chat_name_and_messages():
    chat = make_chat(name="Operación Norte")
    md = generate_chat_markdown(chat, _conversation())
    assert "# Operación Norte" in md
    assert "El plan es avanzar." in md


def test_chat_markdown_labels_user_and_ai():
    chat = make_chat()
    md = generate_chat_markdown(chat, _conversation())
    assert "**User**" in md
    assert "**AI**" in md


def test_chat_markdown_reports_message_count():
    chat = make_chat()
    md = generate_chat_markdown(chat, _conversation())
    assert "3 message(s)" in md


def test_chat_markdown_empty_conversation():
    md = generate_chat_markdown(make_chat(name="Vacío"), [])
    assert "# Vacío" in md
    assert "0 message(s)" in md


# ══════════════════════════════════════════════════════════════════════════════
# generate_chat_pdf
# ══════════════════════════════════════════════════════════════════════════════

def test_chat_pdf_returns_pdf_bytes():
    pdf = generate_chat_pdf(make_chat(name="Informe"), _conversation())
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b"%PDF"


def test_chat_pdf_handles_empty_conversation():
    assert generate_chat_pdf(make_chat(), [])[:4] == b"%PDF"


def test_chat_pdf_raises_on_pisa_error(mocker):
    mocker.patch("core.export.pdf_export.pisa.CreatePDF", return_value=mocker.Mock(err=1))
    with pytest.raises(PDFGenerationException):
        generate_chat_pdf(make_chat(), _conversation())


# ══════════════════════════════════════════════════════════════════════════════
# generate_message_pdf
# ══════════════════════════════════════════════════════════════════════════════

def test_message_pdf_returns_pdf_bytes():
    msg = make_message(sender_type="assistant", message="# Respuesta\n\nDetalle.")
    pdf = generate_message_pdf(make_chat(), msg)
    assert pdf[:4] == b"%PDF"


def test_message_pdf_raises_on_pisa_error(mocker):
    mocker.patch("core.export.pdf_export.pisa.CreatePDF", return_value=mocker.Mock(err=1))
    with pytest.raises(PDFGenerationException):
        generate_message_pdf(make_chat(), make_message())
