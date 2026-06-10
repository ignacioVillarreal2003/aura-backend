import concurrent.futures
import datetime
import html
import io
import logging
from xhtml2pdf import pisa

from apps.artifact_document_action.exceptions import DocumentActionExportException
from apps.artifact_document_action.models import ArtifactDocumentAction

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
        logger.error("xhtml2pdf reported %d error(s) during document-action PDF generation", result.err)
        raise DocumentActionExportException()
    return buf.getvalue()


def _build_pdf(html_content: str) -> bytes:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_build_pdf_sync, html_content)
        try:
            return future.result(timeout=_PDF_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            logger.error("Document-action PDF generation timed out after %ds", _PDF_TIMEOUT_SECONDS)
            raise DocumentActionExportException()


def generate_document_action_pdf(obj: ArtifactDocumentAction) -> bytes:
    created = html.escape(_fmt_dt(obj.created_at))
    action_label = f" ({html.escape(obj.action)})" if obj.action else ""
    html_doc = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>{_CSS}</style>
</head>
<body>
<div class="doc-header">
  <div class="classification">ACCIÓN SOBRE DOCUMENTO{action_label}</div>
</div>
<h1>{html.escape(obj.title)}</h1>
<div class="meta">Generado: {created}</div>
<h2>Instrucción</h2>
<p>{html.escape(obj.instruction)}</p>
<h2>Resultado</h2>
<p>{html.escape(obj.result)}</p>
<div class="doc-footer">
  ACCIÓN SOBRE DOCUMENTO — {created}
</div>
</body>
</html>"""
    return _build_pdf(html_doc)


def generate_document_action_markdown(obj: ArtifactDocumentAction) -> str:
    action_label = f" ({obj.action})" if obj.action else ""
    lines = [
        f"# ACCIÓN SOBRE DOCUMENTO{action_label}",
        "",
        f"**{obj.title}**",
        "",
        f"*Generado: {_fmt_dt(obj.created_at)}*",
        "",
        "---",
        "",
        "## Instrucción",
        "",
        obj.instruction.strip(),
        "",
        "## Resultado",
        "",
        obj.result.strip(),
        "",
        "---",
        "*Acción sobre documento exportada desde AURA*",
    ]
    return "\n".join(lines)
