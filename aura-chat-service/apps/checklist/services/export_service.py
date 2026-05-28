import concurrent.futures
import datetime
import html
import io
import logging
from xhtml2pdf import pisa

from apps.checklist.exceptions import ChecklistExportException
from apps.checklist.models import Checklist

logger = logging.getLogger(__name__)

_PDF_TIMEOUT_SECONDS = 30

_CSS = """
@page {
    size: A4;
    margin: 2.5cm 2cm;
}
body {
    font-family: Courier, monospace;
    font-size: 9pt;
    color: #111111;
    line-height: 1.6;
}
.doc-header {
    border-top: 3px solid #111111;
    border-bottom: 3px solid #111111;
    padding: 8px 0;
    margin-bottom: 18px;
    text-align: center;
}
.classification {
    font-size: 11pt;
    font-weight: bold;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: #000000;
}
.doc-footer {
    border-top: 2px solid #111111;
    padding-top: 4px;
    margin-top: 18px;
    text-align: center;
    font-size: 7.5pt;
    color: #333333;
}
.meta {
    font-size: 8pt;
    color: #555555;
    margin-bottom: 14px;
    font-family: Helvetica, Arial, sans-serif;
}
h1 { font-size: 13pt; margin: 6px 0; font-family: Courier, monospace; }
h2 { font-size: 11pt; margin: 12px 0 4px 0; font-family: Courier, monospace; border-bottom: 1px solid #cccccc; }
.cl-item {
    margin: 3px 0;
    padding: 2px 0 2px 4px;
    font-size: 9pt;
    display: block;
}
.cl-item.checked {
    color: #555555;
    text-decoration: line-through;
}
.cl-checkbox {
    font-family: Courier, monospace;
    margin-right: 6px;
}
.progress {
    font-size: 8pt;
    color: #555555;
    margin-bottom: 10px;
    font-family: Helvetica, Arial, sans-serif;
}
"""


def _fmt_dt(dt) -> str:
    if dt is None:
        return ""
    utc = dt.astimezone(datetime.timezone.utc) if dt.tzinfo else dt
    return utc.strftime("%Y-%m-%d %H:%M UTC")


def _group_items_by_section(items: list) -> dict[str, list]:
    sections: dict[str, list] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        section = str(item.get("section", "General"))
        sections.setdefault(section, []).append(item)
    for sec in sections:
        sections[sec].sort(key=lambda x: int(x.get("order", 0)))
    return sections


def _build_pdf_sync(html_content: str) -> bytes:
    buf = io.BytesIO()
    result = pisa.CreatePDF(io.StringIO(html_content), dest=buf, encoding="utf-8")
    if result.err:
        logger.error("xhtml2pdf reported %d error(s) during checklist PDF generation", result.err)
        raise ChecklistExportException()
    return buf.getvalue()


def _build_pdf(html_content: str) -> bytes:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_build_pdf_sync, html_content)
        try:
            return future.result(timeout=_PDF_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            logger.error("Checklist PDF generation timed out after %ds", _PDF_TIMEOUT_SECONDS)
            raise ChecklistExportException()


def generate_checklist_pdf(checklist: Checklist) -> bytes:
    items = checklist.items if isinstance(checklist.items, list) else []
    total = len(items)
    checked = sum(1 for it in items if isinstance(it, dict) and it.get("is_checked"))
    mode_label = "Con documentos de contexto" if checklist.mode == Checklist.Mode.RAG else "Directo"
    created = html.escape(_fmt_dt(checklist.created_at))

    sections = _group_items_by_section(items)

    sections_html = ""
    for section_name, section_items in sections.items():
        sections_html += f"<h2>{html.escape(section_name)}</h2>\n"
        for item in section_items:
            is_checked = bool(item.get("is_checked"))
            checkbox = "&#9746;" if is_checked else "&#9744;"
            text = html.escape(str(item.get("text", "")))
            cls = "cl-item checked" if is_checked else "cl-item"
            sections_html += (
                f'<span class="{cls}"><span class="cl-checkbox">{checkbox}</span>{text}</span>\n'
            )

    html_doc = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>{_CSS}</style>
</head>
<body>
<div class="doc-header">
  <div class="classification">CLASIFICACIÓN SEGÚN CONTENIDO</div>
</div>
<h1>CHECKLIST DE PROCEDIMIENTO</h1>
<h2 style="border:none; margin-top:2px;">{html.escape(checklist.title)}</h2>
<div class="meta">Generado: {created} &bull; Modo: {mode_label}</div>
<div class="progress">Progreso: {checked}/{total} ítems verificados</div>
<hr/>
{sections_html}
<div class="doc-footer">
  CLASIFICACIÓN SEGÚN CONTENIDO — CHECKLIST — {created}
</div>
</body>
</html>"""

    return _build_pdf(html_doc)


def generate_checklist_markdown(checklist: Checklist) -> str:
    items = checklist.items if isinstance(checklist.items, list) else []
    total = len(items)
    checked = sum(1 for it in items if isinstance(it, dict) and it.get("is_checked"))

    sections = _group_items_by_section(items)

    lines = [
        "# CHECKLIST DE PROCEDIMIENTO",
        "",
        f"**{checklist.title}**",
        "",
        f"*Generado: {_fmt_dt(checklist.created_at)}*",
        "",
        f"*Progreso: {checked}/{total} ítems verificados*",
        "",
        "---",
        "",
    ]

    for section_name, section_items in sections.items():
        lines.append(f"## {section_name}")
        lines.append("")
        for item in section_items:
            is_checked = bool(item.get("is_checked"))
            checkbox = "[x]" if is_checked else "[ ]"
            text = str(item.get("text", ""))
            notes = str(item.get("notes", "")).strip()
            lines.append(f"- {checkbox} {text}")
            if notes:
                lines.append(f"  > {notes}")
        lines.append("")

    lines += ["---", "*Checklist exportada desde AURA*"]
    return "\n".join(lines)
