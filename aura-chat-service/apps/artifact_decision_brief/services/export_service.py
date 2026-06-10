import concurrent.futures
import datetime
import html
import io
import logging
from xhtml2pdf import pisa

from apps.artifact.models.artifact import Artifact
from apps.artifact_decision_brief.exceptions import DecisionBriefExportException
from apps.artifact_decision_brief.models import ArtifactDecisionBrief

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
.opt { margin: 6px 0; padding: 3px 0 3px 6px; border-left: 2px solid #999999; }
.opt.recommended { border-left: 3px solid #111111; }
.opt-title { font-size: 9.5pt; font-weight: bold; }
.opt-meta { font-size: 8.5pt; color: #444444; margin: 1px 0; }
.rec-box { border: 2px solid #111111; padding: 6px 8px; margin-top: 10px; }
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
        logger.error("xhtml2pdf reported %d error(s) during decision-brief PDF generation", result.err)
        raise DecisionBriefExportException()
    return buf.getvalue()


def _build_pdf(html_content: str) -> bytes:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_build_pdf_sync, html_content)
        try:
            return future.result(timeout=_PDF_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            logger.error("Decision-brief PDF generation timed out after %ds", _PDF_TIMEOUT_SECONDS)
            raise DecisionBriefExportException()


def _section(title: str, body: str) -> str:
    if not body.strip():
        return ""
    return f"<h2>{html.escape(title)}</h2><p>{html.escape(body)}</p>\n"


def generate_decision_brief_pdf(brief: ArtifactDecisionBrief) -> bytes:
    options = list(brief.options.all())
    mode_label = "Con documentos de contexto" if brief.artifact.mode == Artifact.Mode.RAG else "Directo"
    created = html.escape(_fmt_dt(brief.created_at))

    options_html = ""
    if options:
        options_html += "<h2>Opciones</h2>\n"
        for idx, opt in enumerate(options, start=1):
            cls = "opt recommended" if opt.is_recommended else "opt"
            star = " &#9733;" if opt.is_recommended else ""
            options_html += f'<div class="{cls}"><div class="opt-title">{idx}. {html.escape(opt.title)}{star}</div>\n'
            if opt.description.strip():
                options_html += f'<div class="opt-meta">{html.escape(opt.description)}</div>\n'
            if opt.pros.strip():
                options_html += f'<div class="opt-meta"><b>A favor:</b> {html.escape(opt.pros)}</div>\n'
            if opt.cons.strip():
                options_html += f'<div class="opt-meta"><b>En contra:</b> {html.escape(opt.cons)}</div>\n'
            options_html += "</div>\n"

    rec_html = ""
    if brief.recommendation.strip():
        rec_html = f'<div class="rec-box"><b>Recomendación:</b> {html.escape(brief.recommendation)}</div>'

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
<h1>BRIEF DE DECISIÓN</h1>
<h2 style="border:none; margin-top:2px;">{html.escape(brief.title)}</h2>
<div class="meta">Generado: {created} &bull; Modo: {mode_label}</div>
{_section("Problema", brief.problem)}
{_section("Contexto", brief.context)}
{options_html}
{_section("Riesgos", brief.risks)}
{rec_html}
<div class="doc-footer">
  CLASIFICACIÓN SEGÚN CONTENIDO — BRIEF DE DECISIÓN — {created}
</div>
</body>
</html>"""

    return _build_pdf(html_doc)


def generate_decision_brief_markdown(brief: ArtifactDecisionBrief) -> str:
    options = list(brief.options.all())

    lines = [
        "# BRIEF DE DECISIÓN",
        "",
        f"**{brief.title}**",
        "",
        f"*Generado: {_fmt_dt(brief.created_at)}*",
        "",
        "---",
        "",
    ]
    if brief.problem.strip():
        lines += ["## Problema", "", brief.problem.strip(), ""]
    if brief.context.strip():
        lines += ["## Contexto", "", brief.context.strip(), ""]

    if options:
        lines += ["## Opciones", ""]
        for idx, opt in enumerate(options, start=1):
            star = " ⭐" if opt.is_recommended else ""
            lines.append(f"### {idx}. {opt.title}{star}")
            if opt.description.strip():
                lines += ["", opt.description.strip()]
            if opt.pros.strip():
                lines.append(f"- **A favor:** {opt.pros}")
            if opt.cons.strip():
                lines.append(f"- **En contra:** {opt.cons}")
            lines.append("")

    if brief.risks.strip():
        lines += ["## Riesgos", "", brief.risks.strip(), ""]
    if brief.recommendation.strip():
        lines += ["## Recomendación", "", brief.recommendation.strip(), ""]

    lines += ["---", "*Brief de decisión exportado desde AURA*"]
    return "\n".join(lines)
