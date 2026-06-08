import concurrent.futures
import datetime
import html
import io
import logging
from xhtml2pdf import pisa

from apps.artifact_document_summary.exceptions import DocumentSummaryExportException
from apps.artifact_document_summary.models import ArtifactDocumentSummary

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
p { white-space: pre-wrap; }
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
    result = pisa.CreatePDF(
        io.StringIO(html_content), dest=buf, encoding="utf-8", link_callback=_safe_link_callback
    )
    if result.err:
        logger.error("xhtml2pdf reported %d error(s) during document-summary PDF generation", result.err)
        raise DocumentSummaryExportException()
    return buf.getvalue()


def _build_pdf(html_content: str) -> bytes:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_build_pdf_sync, html_content)
        try:
            return future.result(timeout=_PDF_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            logger.error("Document-summary PDF generation timed out after %ds", _PDF_TIMEOUT_SECONDS)
            raise DocumentSummaryExportException()


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
<h1>{html.escape(obj.artifact.title)}</h1>
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
        f"**{obj.artifact.title}**",
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
