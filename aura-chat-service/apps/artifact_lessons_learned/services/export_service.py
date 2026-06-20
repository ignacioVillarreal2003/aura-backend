import html
import logging

from core.export import pdf_export
from apps.artifact_lessons_learned.exceptions import LessonsLearnedExportException
from apps.artifact_lessons_learned.models import ArtifactLessonsLearned, ArtifactLessonsLearnedItem

logger = logging.getLogger(__name__)

_CSS = pdf_export.DOC_BASE_CSS + """
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


def _fmt_dt(dt) -> str:
    return pdf_export.fmt_dt(dt)


def _build_pdf(html_content: str) -> bytes:
    return pdf_export.build_pdf(html_content, exc_factory=LessonsLearnedExportException, label="lessons-learned")


def _grouped_items(ll: ArtifactLessonsLearned) -> dict:
    grouped: dict = {cat: [] for cat in _CATEGORY_ORDER}
    for item in ll.items.all():
        grouped.setdefault(item.category, []).append(item)
    return grouped


def generate_lessons_learned_pdf(ll: ArtifactLessonsLearned) -> bytes:
    mode_label = "Con documentos de contexto" if (ll.artifact.retrieve_context or ll.artifact.process_documents) else "Directo"
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
