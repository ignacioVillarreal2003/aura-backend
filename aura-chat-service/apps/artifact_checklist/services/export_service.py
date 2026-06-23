import html
import logging

from core.export import pdf_export
from apps.artifact_checklist.exceptions import ChecklistExportException
from apps.artifact_checklist.models import ArtifactChecklist

logger = logging.getLogger(__name__)

_CSS = pdf_export.DOC_BASE_CSS + """
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


def _build_pdf(html_content: str) -> bytes:
    return pdf_export.build_pdf(html_content, exc_factory=ChecklistExportException, label="checklist")


def generate_checklist_pdf(checklist: ArtifactChecklist) -> bytes:
    sections = list(checklist.sections.all())
    all_items = [item for sec in sections for item in sec.items.all()]
    total = len(all_items)
    checked = sum(1 for it in all_items if it.is_checked)
    created = html.escape(pdf_export.fmt_dt(checklist.created_at))
    description_html = f"<p>{html.escape(checklist.description)}</p>" if checklist.description else ""

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
<h1>CHECKLIST DE PROCEDIMIENTO</h1>
<h2 style="border:none; margin-top:2px;">{html.escape(checklist.title)}</h2>
<div class="meta">Generado: {created} &bull; {checked}/{total} ítems verificados</div>
{description_html}
<hr/>
{sections_html}
<div class="doc-footer">
  CHECKLIST — {created}
</div>
</body>
</html>"""

    return _build_pdf(html_doc)


def generate_checklist_markdown(checklist: ArtifactChecklist) -> str:
    sections = list(checklist.sections.all())
    all_items = [item for sec in sections for item in sec.items.all()]
    total = len(all_items)
    checked = sum(1 for it in all_items if it.is_checked)

    lines = ["# Checklist de procedimiento", ""]
    if (checklist.title or "").strip():
        lines += [f"## {checklist.title.strip()}", ""]
    if (checklist.description or "").strip():
        lines += [checklist.description.strip(), ""]
    lines += [
        f"_Generado: {pdf_export.fmt_dt(checklist.created_at)} · {checked}/{total} ítems verificados_",
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
        lines.append("")

    lines += ["---", "", "_Exportado desde AURA_"]
    return "\n".join(lines)
