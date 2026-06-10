import concurrent.futures
import datetime
import html
import io
import logging
from xhtml2pdf import pisa

from apps.artifact.models.artifact import Artifact
from apps.artifact_timeline.exceptions import TimelineExportException
from apps.artifact_timeline.models import ArtifactTimeline

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
.tl-event {
    margin: 6px 0;
    padding: 4px 0 4px 8px;
    border-left: 2px solid #888888;
}
.tl-when {
    font-size: 8pt;
    font-weight: bold;
    color: #333333;
    font-family: Helvetica, Arial, sans-serif;
}
.tl-title { font-size: 9.5pt; font-weight: bold; margin: 1px 0; }
.tl-desc { font-size: 8.5pt; color: #444444; }
"""


def _fmt_dt(dt) -> str:
    if dt is None:
        return ""
    utc = dt.astimezone(datetime.timezone.utc) if dt.tzinfo else dt
    return utc.strftime("%Y-%m-%d %H:%M UTC")


def _event_when(event) -> str:
    return event.occurred_label or "—"


def _build_pdf_sync(html_content: str) -> bytes:
    buf = io.BytesIO()
    result = pisa.CreatePDF(io.StringIO(html_content), dest=buf, encoding="utf-8")
    if result.err:
        logger.error("xhtml2pdf reported %d error(s) during timeline PDF generation", result.err)
        raise TimelineExportException()
    return buf.getvalue()


def _build_pdf(html_content: str) -> bytes:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_build_pdf_sync, html_content)
        try:
            return future.result(timeout=_PDF_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            logger.error("ArtifactTimeline PDF generation timed out after %ds", _PDF_TIMEOUT_SECONDS)
            raise TimelineExportException()


def generate_timeline_pdf(timeline: ArtifactTimeline) -> bytes:
    events = list(timeline.events.all())
    mode_label = "Con documentos de contexto" if timeline.artifact.mode == Artifact.Mode.RAG else "Directo"
    created = html.escape(_fmt_dt(timeline.created_at))

    events_html = ""
    for event in events:
        when = html.escape(_event_when(event))
        title = html.escape(event.title)
        desc = html.escape(event.description)
        desc_html = f'<div class="tl-desc">{desc}</div>' if desc else ""
        events_html += (
            f'<div class="tl-event"><div class="tl-when">{when}</div>'
            f'<div class="tl-title">{title}</div>{desc_html}</div>\n'
        )

    summary_html = f"<p>{html.escape(timeline.summary)}</p>" if timeline.summary else ""

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
<h1>LÍNEA DE TIEMPO</h1>
<h2 style="border:none; margin-top:2px;">{html.escape(timeline.title)}</h2>
<div class="meta">Generado: {created} &bull; Modo: {mode_label} &bull; {len(events)} eventos</div>
{summary_html}
<hr/>
{events_html}
<div class="doc-footer">
  CLASIFICACIÓN SEGÚN CONTENIDO — LÍNEA DE TIEMPO — {created}
</div>
</body>
</html>"""

    return _build_pdf(html_doc)


def generate_timeline_markdown(timeline: ArtifactTimeline) -> str:
    events = list(timeline.events.all())

    lines = [
        "# LÍNEA DE TIEMPO",
        "",
        f"**{timeline.title}**",
        "",
        f"*Generado: {_fmt_dt(timeline.created_at)}*",
        "",
    ]
    if (timeline.summary or "").strip():
        lines += [timeline.summary.strip(), ""]
    lines += ["---", ""]

    for event in events:
        lines.append(f"### {_event_when(event)} — {event.title}")
        if event.description.strip():
            lines.append("")
            lines.append(event.description.strip())
        lines.append("")

    lines += ["---", "*Línea de tiempo exportada desde AURA*"]
    return "\n".join(lines)
