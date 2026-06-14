import html
import logging

from core.export import pdf_export
from apps.artifact_document_summary.exceptions import DocumentSummaryExportException
from apps.artifact_document_summary.models import ArtifactDocumentSummary

logger = logging.getLogger(__name__)

_CSS = pdf_export.DOC_BASE_CSS + """
h2 { font-size: 11pt; margin: 12px 0 4px 0; font-family: Courier, monospace; border-bottom: 1px solid #cccccc; }
p { white-space: pre-wrap; }
"""


def _fmt_dt(dt) -> str:
    return pdf_export.fmt_dt(dt)


def _build_pdf(html_content: str) -> bytes:
    return pdf_export.build_pdf(html_content, exc_factory=DocumentSummaryExportException, label="document-summary")


def generate_document_summary_pdf(obj: ArtifactDocumentSummary) -> bytes:
    created = html.escape(_fmt_dt(obj.created_at))
    html_doc = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>{_CSS}</style>
</head>
<body>
<div class="doc-header">
  <div class="classification">RESUMEN DE DOCUMENTO</div>
</div>
<h1>{html.escape(obj.title)}</h1>
<div class="meta">Generado: {created}</div>
<h2>Resumen</h2>
<p>{html.escape(obj.summary)}</p>
<div class="doc-footer">
  RESUMEN DE DOCUMENTO — {created}
</div>
</body>
</html>"""
    return _build_pdf(html_doc)


def generate_document_summary_markdown(obj: ArtifactDocumentSummary) -> str:
    lines = [
        "# RESUMEN DE DOCUMENTO",
        "",
        f"**{obj.title}**",
        "",
        f"*Generado: {_fmt_dt(obj.created_at)}*",
        "",
        "---",
        "",
        "## Resumen",
        "",
        obj.summary.strip(),
        "",
        "---",
        "*Resumen de documento exportado desde AURA*",
    ]
    return "\n".join(lines)
