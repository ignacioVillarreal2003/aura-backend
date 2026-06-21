"""
Unit tests for the checklist export service (PDF / Markdown rendering).

Previously untested: the view-layer tests mock `generate_checklist_pdf` /
`generate_checklist_markdown` entirely.

The export functions traverse the ORM relations (`checklist.sections.all()`,
`section.items.all()`), so these tests build lightweight stand-ins that expose
an `.all()` callable instead of reusing the list-based conftest factories.
"""
import datetime
from types import SimpleNamespace

import pytest

from apps.artifact_checklist.exceptions import ChecklistExportException
from apps.artifact_checklist.models import ArtifactChecklist
from core.export.pdf_export import fmt_dt as _fmt_dt
from apps.artifact_checklist.services.export_service import (
    generate_checklist_markdown,
    generate_checklist_pdf,
)

EXPORT = "apps.artifact_checklist.services.export_service"


def _item(text="Item", is_checked=False, notes=""):
    return SimpleNamespace(text=text, is_checked=is_checked, notes=notes)


def _section(title="Sección", items=None):
    items = items or []
    return SimpleNamespace(title=title, items=SimpleNamespace(all=lambda: items))


def _checklist(title="Mi checklist", retrieve_context=None, process_documents=None, sections=None, created_at=None):
    sections = sections or []
    return SimpleNamespace(
        title=title,
        artifact=SimpleNamespace(retrieve_context=retrieve_context, process_documents=process_documents),
        created_at=created_at or datetime.datetime(2025, 3, 15, 9, 30, tzinfo=datetime.timezone.utc),
        sections=SimpleNamespace(all=lambda: sections),
    )


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
# generate_checklist_markdown
# ══════════════════════════════════════════════════════════════════════════════

def test_markdown_includes_title_and_footer():
    cl = _checklist(title="Mantenimiento", sections=[_section("S", items=[_item("a")])])
    md = generate_checklist_markdown(cl)
    assert "Mantenimiento" in md
    assert "exportada desde AURA" in md


def test_markdown_includes_section_titles():
    sections = [_section("Preparación", items=[_item("x")]), _section("Ejecución", items=[_item("y")])]
    md = generate_checklist_markdown(_checklist(sections=sections))
    assert "## Preparación" in md
    assert "## Ejecución" in md


def test_markdown_renders_checkbox_states():
    sections = [_section("S", items=[_item("hecho", is_checked=True), _item("pendiente", is_checked=False)])]
    md = generate_checklist_markdown(_checklist(sections=sections))
    assert "- [x] hecho" in md
    assert "- [ ] pendiente" in md


def test_markdown_progress_counts_checked_items():
    items = [_item("a", is_checked=True), _item("b", is_checked=False), _item("c", is_checked=True)]
    md = generate_checklist_markdown(_checklist(sections=[_section("S", items=items)]))
    assert "Progreso: 2/3" in md


def test_markdown_includes_notes_as_blockquote():
    sections = [_section("S", items=[_item("tarea", notes="cuidado aquí")])]
    md = generate_checklist_markdown(_checklist(sections=sections))
    assert "> cuidado aquí" in md


def test_markdown_omits_blank_notes():
    sections = [_section("S", items=[_item("tarea", notes="   ")])]
    md = generate_checklist_markdown(_checklist(sections=sections))
    assert "  >" not in md


def test_markdown_empty_checklist_reports_zero_progress():
    md = generate_checklist_markdown(_checklist(sections=[]))
    assert "Progreso: 0/0" in md


def test_markdown_returns_str():
    assert isinstance(generate_checklist_markdown(_checklist()), str)


# ══════════════════════════════════════════════════════════════════════════════
# generate_checklist_pdf
# ══════════════════════════════════════════════════════════════════════════════

def test_pdf_returns_pdf_bytes():
    sections = [_section("Fase 1", items=[_item("Revisar motor"), _item("Cargar combustible", is_checked=True)])]
    pdf = generate_checklist_pdf(_checklist(sections=sections))
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b"%PDF"


def test_pdf_handles_rag_mode():
    cl = _checklist(process_documents=True, sections=[_section("S", items=[_item("a")])])
    assert generate_checklist_pdf(cl)[:4] == b"%PDF"


def test_pdf_handles_empty_sections():
    assert generate_checklist_pdf(_checklist(sections=[]))[:4] == b"%PDF"


def test_pdf_raises_export_exception_on_pisa_error(mocker):
    mocker.patch("core.export.pdf_export.pisa.CreatePDF", return_value=mocker.Mock(err=1))
    with pytest.raises(ChecklistExportException):
        generate_checklist_pdf(_checklist(sections=[_section("S", items=[_item("a")])]))
