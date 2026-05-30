import concurrent.futures
import html
import io
import logging
import re

import markdown as md_lib
from xhtml2pdf import pisa

from apps.report.exceptions import ReportExportException
from apps.report.models import Report

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
h2 { font-size: 11pt; margin: 8px 0 3px 0; font-family: Courier, monospace; border-bottom: 1px solid #cccccc; }
h3 { font-size: 10pt; margin: 6px 0 2px 0; font-family: Courier, monospace; }
p { margin: 2px 0 6px 0; }
pre {
    background-color: #F5F5F5;
    padding: 5px 7px;
    font-size: 8pt;
    font-family: Courier, monospace;
    white-space: pre-wrap;
    word-wrap: break-word;
}
code {
    background-color: #F0F0F0;
    font-family: Courier, monospace;
    font-size: 8pt;
    padding: 0 3px;
}
ul, ol { margin: 3px 0; padding-left: 18px; }
li { margin: 1px 0; }
table {
    border-collapse: collapse;
    width: 100%;
    margin: 6px 0;
}
th, td {
    border: 1px solid #999999;
    padding: 3px 7px;
    font-size: 8.5pt;
    text-align: left;
}
th { background-color: #E8E8E8; font-weight: bold; }
blockquote {
    border-left: 3px solid #888888;
    margin: 3px 0;
    padding-left: 8px;
    color: #555555;
    font-style: italic;
}
hr { border: 1px solid #cccccc; margin: 8px 0; }
"""

_TYPE_LABELS = {
    Report.Type.SITREP: "INFORME DE SITUACIÓN",
    Report.Type.INTSUM: "RESUMEN DE INTELIGENCIA",
    Report.Type.OPORD: "ORDEN DE OPERACIONES",
}


_DANGEROUS_TAGS_RE = re.compile(
    r"<\s*/?\s*(script|style|iframe|object|embed|form|input|button|textarea)\b[^>]*>",
    re.IGNORECASE,
)


def _render_markdown(text: str) -> str:
    raw_html = md_lib.markdown(text, extensions=["fenced_code", "tables", "nl2br"])
    return _DANGEROUS_TAGS_RE.sub("", raw_html)


def _fmt_dt(dt) -> str:
    if dt is None:
        return ""
    import datetime
    utc = dt.astimezone(datetime.timezone.utc) if dt.tzinfo else dt
    return utc.strftime("%Y-%m-%d %H:%M UTC")


def _build_pdf_sync(html_content: str) -> bytes:
    buf = io.BytesIO()
    result = pisa.CreatePDF(io.StringIO(html_content), dest=buf, encoding="utf-8")
    if result.err:
        logger.error("xhtml2pdf reported %d error(s) during report PDF generation", result.err)
        raise ReportExportException()
    return buf.getvalue()


def _build_pdf(html_content: str) -> bytes:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_build_pdf_sync, html_content)
        try:
            return future.result(timeout=_PDF_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            logger.error("Report PDF generation timed out after %ds", _PDF_TIMEOUT_SECONDS)
            raise ReportExportException()


def generate_report_pdf(report: Report) -> bytes:
    type_label = html.escape(_TYPE_LABELS.get(report.type, report.type))
    title = html.escape(report.title)
    created = html.escape(_fmt_dt(report.created_at))
    mode_label = "Con documentos de contexto" if report.mode == Report.Mode.RAG else "Directo"
    content_html = _render_markdown(report.content)

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
<h1>{type_label}</h1>
<h2>{title}</h2>
<div class="meta">
  Generado: {created} &bull; Modo: {mode_label}
</div>
<hr/>
{content_html}
<div class="doc-footer">
  CLASIFICACIÓN SEGÚN CONTENIDO — {type_label} — {created}
</div>
</body>
</html>"""

    return _build_pdf(html_doc)


def generate_report_markdown(report: Report) -> str:
    type_label = _TYPE_LABELS.get(report.type, report.type)
    lines = [
        f"# {type_label}",
        "",
        f"**{report.title}**",
        "",
        f"*Generado: {_fmt_dt(report.created_at)}*",
        "",
        "---",
        "",
        report.content,
        "",
        "---",
        f"*{type_label} — Exportado desde AURA*",
    ]
    return "\n".join(lines)
