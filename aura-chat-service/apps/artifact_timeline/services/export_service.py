import html
import logging

from core.export import pdf_export
from apps.artifact_timeline.exceptions import TimelineExportException
from apps.artifact_timeline.models import ArtifactTimeline

logger = logging.getLogger(__name__)

_CSS = pdf_export.DOC_BASE_CSS + """
.tl-event {
    margin: 8px 0;
}
.tl-when {
    font-size: 8pt;
    font-weight: bold;
    color: #333333;
    font-family: Helvetica, Arial, sans-serif;
}
.tl-title { font-size: 9.5pt; font-weight: bold; margin: 1px 0; }
.tl-desc { font-size: 8.5pt; color: #444444; margin-bottom: 18px; }
.tl-desc p { margin: 0 0 4px; }
.tl-desc ul, .tl-desc ol { margin: 2px 0 4px; padding-left: 16px; }
.tl-desc li { margin: 1px 0; }
"""


def _fmt_dt(dt) -> str:
    return pdf_export.fmt_dt(dt)


def _event_when(event) -> str:
    return event.occurred_label or "—"


def _count_label(count: int) -> str:
    return f"{count} evento{'s' if count != 1 else ''}"


def _build_pdf(html_content: str) -> bytes:
    return pdf_export.build_pdf(html_content, exc_factory=TimelineExportException, label="timeline")


def generate_timeline_pdf(timeline: ArtifactTimeline) -> bytes:
    events = list(timeline.events.all())
    created = html.escape(_fmt_dt(timeline.created_at))

    events_html = ""
    for event in events:
        when = html.escape(_event_when(event))
        title = html.escape(event.title)
        desc = (event.description or "").strip()
        desc_html = f'<div class="tl-desc">{pdf_export.render_markdown(desc)}</div>' if desc else ""
        events_html += (
            f'<div class="tl-event"><div class="tl-when">{when}</div>'
            f'<div class="tl-title">{title}</div>{desc_html}</div>\n'
        )

    description_html = f"<p>{html.escape(timeline.description)}</p>" if timeline.description else ""

    html_doc = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>{_CSS}</style>
</head>
<body>
<h1>LÍNEA DE TIEMPO</h1>
<h2 style="border:none; margin-top:2px;">{html.escape(timeline.title)}</h2>
<div class="meta">Generado: {created} &bull; {_count_label(len(events))}</div>
{description_html}
<hr/>
{events_html}
<div class="doc-footer">
  LÍNEA DE TIEMPO — {created}
</div>
</body>
</html>"""

    return _build_pdf(html_doc)


def generate_timeline_markdown(timeline: ArtifactTimeline) -> str:
    events = list(timeline.events.all())

    lines = ["# Línea de tiempo", ""]
    if (timeline.title or "").strip():
        lines += [f"## {timeline.title.strip()}", ""]
    if (timeline.description or "").strip():
        lines += [timeline.description.strip(), ""]
    lines += [
        f"_Generado: {_fmt_dt(timeline.created_at)} · {_count_label(len(events))}_",
        "",
        "---",
        "",
    ]

    for idx, event in enumerate(events, start=1):
        lines.append(f"### {idx}. {(event.title or '').strip()}".rstrip())
        when = (event.occurred_label or "").strip()
        if when:
            lines += ["", f"*{when}*"]
        desc = (event.description or "").strip()
        if desc:
            lines += ["", desc]
        lines.append("")

    lines += ["---", "", "_Exportado desde AURA_"]
    return "\n".join(lines)
