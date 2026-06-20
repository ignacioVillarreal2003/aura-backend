"""
Unit tests for the report export service (PDF / Markdown rendering).

These exercise the pure rendering helpers directly — they were previously
untested because the view-layer tests mock `generate_report_pdf` /
`generate_report_markdown` entirely.
"""
import datetime

import pytest

from apps.artifact_report.exceptions import ReportExportException
from apps.artifact_report.models import ArtifactReport
from apps.artifact_report.services.export_service import (
    _TYPE_LABELS,
    _fmt_dt,
    _render_markdown,
    generate_report_markdown,
    generate_report_pdf,
)
from test.conftest import make_report

EXPORT = "apps.artifact_report.services.export_service"


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
    md = "| A | B |\n| - | - |\n| 1 | 2 |"
    html = _render_markdown(md)
    assert "<table>" in html


def test_render_markdown_strips_script_tags():
    html = _render_markdown("Hola <script>alert('x')</script> mundo")
    assert "<script" not in html.lower()


def test_render_markdown_strips_iframe_tags():
    html = _render_markdown("texto <iframe src='http://evil'></iframe>")
    assert "<iframe" not in html.lower()


def test_render_markdown_strips_form_and_input_tags():
    html = _render_markdown("<form><input name='x'></form>")
    assert "<form" not in html.lower()
    assert "<input" not in html.lower()


# ══════════════════════════════════════════════════════════════════════════════
# generate_report_markdown
# ══════════════════════════════════════════════════════════════════════════════

def test_generate_markdown_includes_title_and_content():
    report = make_report(title="Mi informe", content="Cuerpo del informe")
    md = generate_report_markdown(report)
    assert "Mi informe" in md
    assert "Cuerpo del informe" in md


def test_generate_markdown_uses_human_type_label():
    report = make_report(report_type=ArtifactReport.Type.SITREP)
    md = generate_report_markdown(report)
    assert _TYPE_LABELS[ArtifactReport.Type.SITREP] in md


def test_generate_markdown_unknown_type_falls_back_to_raw_value():
    report = make_report(report_type="CUSTOM")
    md = generate_report_markdown(report)
    assert "CUSTOM" in md


def test_generate_markdown_includes_export_footer():
    md = generate_report_markdown(make_report())
    assert "Exportado desde AURA" in md


def test_generate_markdown_returns_str():
    assert isinstance(generate_report_markdown(make_report()), str)


# ══════════════════════════════════════════════════════════════════════════════
# generate_report_pdf
# ══════════════════════════════════════════════════════════════════════════════

def test_generate_pdf_returns_pdf_bytes():
    report = make_report(title="Informe", content="# Sección\n\nContenido del informe.")
    pdf = generate_report_pdf(report)
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b"%PDF"


def test_generate_pdf_handles_rag_mode():
    report = make_report(process_documents=True, content="Contenido con contexto.")
    pdf = generate_report_pdf(report)
    assert pdf[:4] == b"%PDF"


def test_generate_pdf_raises_export_exception_on_pisa_error(mocker):
    """When xhtml2pdf reports rendering errors, a ReportExportException is raised."""
    report = make_report()
    mocker.patch("core.export.pdf_export.pisa.CreatePDF", return_value=mocker.Mock(err=1))
    with pytest.raises(ReportExportException):
        generate_report_pdf(report)
