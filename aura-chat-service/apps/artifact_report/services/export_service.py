import html
import logging

from core.export import pdf_export
from apps.artifact_report.exceptions import ReportExportException
from apps.artifact_report.models import ArtifactReport

logger = logging.getLogger(__name__)

_CSS = pdf_export.DOC_BASE_CSS + """
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
    ArtifactReport.Type.SITREP: "INFORME DE SITUACIÓN",
    ArtifactReport.Type.INTSUM: "RESUMEN DE INTELIGENCIA",
    ArtifactReport.Type.OPORD: "ORDEN DE OPERACIONES",
}


def _render_markdown(text: str) -> str:
    return pdf_export.render_markdown(text)


def _fmt_dt(dt) -> str:
    return pdf_export.fmt_dt(dt)


def _build_pdf(html_content: str) -> bytes:
    return pdf_export.build_pdf(html_content, exc_factory=ReportExportException, label="report")


def generate_report_pdf(report: ArtifactReport) -> bytes:
    type_label = html.escape(_TYPE_LABELS.get(report.type, report.type))
    title = html.escape(report.title)
    created = html.escape(_fmt_dt(report.created_at))
    mode_label = "Con documentos de contexto" if (report.artifact.retrieve_context or report.artifact.process_documents) else "Directo"
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


def generate_report_markdown(report: ArtifactReport) -> str:
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
