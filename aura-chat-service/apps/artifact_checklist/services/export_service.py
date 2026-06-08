import concurrent.futures
import datetime
import html
import io
import logging
from xhtml2pdf import pisa

from apps.artifact.models.artifact import Artifact
from apps.artifact_checklist.exceptions import ChecklistExportException
from apps.artifact_checklist.models import ArtifactChecklist

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


def _safe_link_callback(uri: str, rel: str) -> str:
    return ""


def _fmt_dt(dt) -> str:
    if dt is None:
        return ""
    utc = dt.astimezone(datetime.timezone.utc) if dt.tzinfo else dt
    return utc.strftime("%Y-%m-%d %H:%M UTC")


def _build_pdf_sync(html_content: str) -> bytes:
    buf = io.BytesIO()
    result = pisa.CreatePDF(io.StringIO(html_content), dest=buf, encoding="utf-8", link_callback=_safe_link_callback)
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
            logger.error("ArtifactChecklist PDF generation timed out after %ds", _PDF_TIMEOUT_SECONDS)
            raise ChecklistExportException()


def generate_checklist_pdf(checklist: ArtifactChecklist) -> bytes:
    sections = list(checklist.sections.all())
    all_items = [item for sec in sections for item in sec.items.all()]
    total = len(all_items)
    checked = sum(1 for it in all_items if it.is_checked)
    mode_label = "Con documentos de contexto" if checklist.artifact.mode == Artifact.Mode.RAG else "Directo"
    created = html.escape(_fmt_dt(checklist.created_at))

    sections_html = ""
    for section in sections:
        sections_html += f"<h2>{html.escape(section.title)}</h2>\n"
        for item in section.items.all():
            checkbox = "&#9746;" if item.is_checked else "&#9744;"
            text = html.escape(item.text)
            cls = "cl-item checked" if item.is_checked else "cl-item"
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
<h2 style="border:none; margin-top:2px;">{html.escape(checklist.artifact.title)}</h2>
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


def generate_checklist_markdown(checklist: ArtifactChecklist) -> str:
    sections = list(checklist.sections.all())
    all_items = [item for sec in sections for item in sec.items.all()]
    total = len(all_items)
    checked = sum(1 for it in all_items if it.is_checked)

    lines = [
        "# CHECKLIST DE PROCEDIMIENTO",
        "",
        f"**{checklist.artifact.title}**",
        "",
        f"*Generado: {_fmt_dt(checklist.created_at)}*",
        "",
        f"*Progreso: {checked}/{total} ítems verificados*",
        "",
        "---",
        "",
    ]

    for section in sections:
        lines.append(f"## {section.title}")
        lines.append("")
        for item in section.items.all():
            checkbox = "[x]" if item.is_checked else "[ ]"
            lines.append(f"- {checkbox} {item.text}")
            if item.notes.strip():
                lines.append(f"  > {item.notes}")
        lines.append("")

    lines += ["---", "*ArtifactChecklist exportada desde AURA*"]
    return "\n".join(lines)
