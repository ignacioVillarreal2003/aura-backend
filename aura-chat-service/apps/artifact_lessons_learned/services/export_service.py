import concurrent.futures
import datetime
import html
import io
import logging
from xhtml2pdf import pisa

from apps.artifact.models.artifact import Artifact
from apps.artifact_lessons_learned.exceptions import LessonsLearnedExportException
from apps.artifact_lessons_learned.models import ArtifactLessonsLearned, ArtifactLessonsLearnedItem

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
.ll-item { margin: 4px 0; padding: 2px 0 2px 6px; border-left: 2px solid #999999; }
.ll-obs { font-size: 9pt; font-weight: bold; }
.ll-rec { font-size: 8.5pt; color: #444444; margin-top: 1px; }
"""

_CATEGORY_LABELS = {
    ArtifactLessonsLearnedItem.Category.SUSTAIN: "Sostener",
    ArtifactLessonsLearnedItem.Category.IMPROVE: "Mejorar",
    ArtifactLessonsLearnedItem.Category.RECOMMENDATION: "Recomendación",
}
_CATEGORY_ORDER = [
    ArtifactLessonsLearnedItem.Category.SUSTAIN,
    ArtifactLessonsLearnedItem.Category.IMPROVE,
    ArtifactLessonsLearnedItem.Category.RECOMMENDATION,
]


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
        logger.error("xhtml2pdf reported %d error(s) during lessons-learned PDF generation", result.err)
        raise LessonsLearnedExportException()
    return buf.getvalue()


def _build_pdf(html_content: str) -> bytes:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_build_pdf_sync, html_content)
        try:
            return future.result(timeout=_PDF_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            logger.error("Lessons-learned PDF generation timed out after %ds", _PDF_TIMEOUT_SECONDS)
            raise LessonsLearnedExportException()


def _grouped_items(ll: ArtifactLessonsLearned) -> dict:
    grouped: dict = {cat: [] for cat in _CATEGORY_ORDER}
    for item in ll.items.all():
        grouped.setdefault(item.category, []).append(item)
    return grouped


def generate_lessons_learned_pdf(ll: ArtifactLessonsLearned) -> bytes:
    mode_label = "Con documentos de contexto" if ll.artifact.mode == Artifact.Mode.RAG else "Directo"
    created = html.escape(_fmt_dt(ll.created_at))
    grouped = _grouped_items(ll)

    context_html = f"<h2>Contexto</h2><p>{html.escape(ll.context)}</p>" if ll.context else ""

    sections_html = ""
    for category in _CATEGORY_ORDER:
        items = grouped.get(category, [])
        if not items:
            continue
        sections_html += f"<h2>{html.escape(_CATEGORY_LABELS[category])}</h2>\n"
        for item in items:
            obs = html.escape(item.observation)
            rec = html.escape(item.recommendation)
            rec_html = f'<div class="ll-rec">&rarr; {rec}</div>' if rec else ""
            sections_html += f'<div class="ll-item"><div class="ll-obs">{obs}</div>{rec_html}</div>\n'

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
<h1>LECCIONES APRENDIDAS</h1>
<h2 style="border:none; margin-top:2px;">{html.escape(ll.title)}</h2>
<div class="meta">Generado: {created} &bull; Modo: {mode_label}</div>
{context_html}
<hr/>
{sections_html}
<div class="doc-footer">
  CLASIFICACIÓN SEGÚN CONTENIDO — LECCIONES APRENDIDAS — {created}
</div>
</body>
</html>"""

    return _build_pdf(html_doc)


def generate_lessons_learned_markdown(ll: ArtifactLessonsLearned) -> str:
    grouped = _grouped_items(ll)

    lines = [
        "# LECCIONES APRENDIDAS",
        "",
        f"**{ll.title}**",
        "",
        f"*Generado: {_fmt_dt(ll.created_at)}*",
        "",
    ]
    if (ll.context or "").strip():
        lines += ["## Contexto", "", ll.context.strip(), ""]
    lines += ["---", ""]

    for category in _CATEGORY_ORDER:
        items = grouped.get(category, [])
        if not items:
            continue
        lines.append(f"## {_CATEGORY_LABELS[category]}")
        lines.append("")
        for item in items:
            lines.append(f"- {item.observation}")
            if item.recommendation.strip():
                lines.append(f"  > {item.recommendation}")
        lines.append("")

    lines += ["---", "*Lecciones aprendidas exportadas desde AURA*"]
    return "\n".join(lines)
