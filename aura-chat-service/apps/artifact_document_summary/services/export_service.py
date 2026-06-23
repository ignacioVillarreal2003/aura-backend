import html
import logging

from core.export import pdf_export
from apps.artifact_document_summary.exceptions import DocumentSummaryExportException
from apps.artifact_document_summary.models import ArtifactDocumentSummary

logger = logging.getLogger(__name__)

_CSS = pdf_export.DOC_BASE_CSS + """
.ds-body { font-size: 8.5pt; color: #444444; }
.ds-body h2 { font-size: 11pt; margin: 14px 0 4px; font-family: Courier, monospace; color: #111111; }
.ds-body h3 { font-size: 9.5pt; margin: 10px 0 3px; font-family: Courier, monospace; color: #111111; }
.ds-body p { margin: 0 0 5px; }
.ds-body ul, .ds-body ol { margin: 3px 0 6px; padding-left: 18px; }
.ds-body li { margin: 1px 0; }
.ds-body table { border-collapse: collapse; margin: 6px 0; width: 100%; }
.ds-body th, .ds-body td { border: 1px solid #cccccc; padding: 3px 6px; font-size: 8pt; text-align: left; }
.ds-body strong { color: #111111; }
"""


def _fmt_dt(dt) -> str:
    return pdf_export.fmt_dt(dt)


def _build_pdf(html_content: str) -> bytes:
    return pdf_export.build_pdf(html_content, exc_factory=DocumentSummaryExportException, label="document-summary")


def generate_document_summary_pdf(obj: ArtifactDocumentSummary) -> bytes:
    created = html.escape(_fmt_dt(obj.created_at))
    description_html = f"<p>{html.escape(obj.description)}</p>" if obj.description else ""
    body_html = f'<div class="ds-body">{pdf_export.render_markdown(obj.summary.strip())}</div>' if obj.summary.strip() else ""

    html_doc = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>{_CSS}</style>
</head>
<body>
<h1>RESUMEN DE DOCUMENTO</h1>
<h2 style="border:none; margin-top:2px;">{html.escape(obj.title)}</h2>
<div class="meta">Generado: {created}</div>
{description_html}
<hr/>
{body_html}
<div class="doc-footer">
  RESUMEN DE DOCUMENTO — {created}
</div>
</body>
</html>"""
    return _build_pdf(html_doc)


def generate_document_summary_markdown(obj: ArtifactDocumentSummary) -> str:
    lines = ["# Resumen de documento", ""]
    if (obj.title or "").strip():
        lines += [f"## {obj.title.strip()}", ""]
    if (obj.description or "").strip():
        lines += [obj.description.strip(), ""]
    lines += [
        f"_Generado: {_fmt_dt(obj.created_at)}_",
        "",
        "---",
        "",
        obj.summary.strip(),
        "",
        "---",
        "",
        "_Exportado desde AURA_",
    ]
    return "\n".join(lines)
