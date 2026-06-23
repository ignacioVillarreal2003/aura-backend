import html
import logging

from core.export import pdf_export
from apps.artifact_lessons_learned.exceptions import LessonsLearnedExportException
from apps.artifact_lessons_learned.models import ArtifactLessonsLearned, ArtifactLessonsLearnedItem

logger = logging.getLogger(__name__)

_CSS = pdf_export.DOC_BASE_CSS + """
.ll-cat {
    font-size: 10pt;
    font-weight: bold;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #111111;
    font-family: Courier, monospace;
    margin: 18px 0 6px;
}
.ll-item {
    margin: 0 0 14px;
}
.ll-flabel {
    font-size: 8.5pt;
    color: #444444;
    font-family: Helvetica, Arial, sans-serif;
    margin: 7px 0 1px;
}
.ll-flabel--obs {
    font-weight: bold;
    color: #111111;
}
.ll-text { font-size: 8.5pt; color: #444444; margin: 0; }
.ll-text p { margin: 0 0 4px; }
.ll-text p:last-child { margin-bottom: 0; }
.ll-text ul, .ll-text ol { margin: 2px 0 4px; padding-left: 16px; }
.ll-text li { margin: 1px 0; }
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


def _count_label(count: int) -> str:
    return f"{count} {'lección' if count == 1 else 'lecciones'}"


def _build_pdf(html_content: str) -> bytes:
    return pdf_export.build_pdf(html_content, exc_factory=LessonsLearnedExportException, label="lessons-learned")


def _grouped_items(ll: ArtifactLessonsLearned) -> dict:
    grouped: dict = {cat: [] for cat in _CATEGORY_ORDER}
    for item in ll.items.all():
        grouped.setdefault(item.category, []).append(item)
    return grouped


def generate_lessons_learned_pdf(ll: ArtifactLessonsLearned) -> bytes:
    created = html.escape(_fmt_dt(ll.created_at))
    grouped = _grouped_items(ll)
    total = sum(len(items) for items in grouped.values())

    sections_html = ""
    for category in _CATEGORY_ORDER:
        items = grouped.get(category, [])
        if not items:
            continue
        sections_html += f'<div class="ll-cat">{html.escape(_CATEGORY_LABELS[category])}</div>\n'
        for item in items:
            obs = html.escape(item.observation)
            disc = (item.discussion or "").strip()
            rec = (item.recommendation or "").strip()
            fields_html = (
                f'<div class="ll-flabel ll-flabel--obs">Observación</div>'
                f'<div class="ll-text">{obs}</div>'
            )
            if disc:
                fields_html += (
                    f'<div class="ll-flabel">Discusión</div>'
                    f'<div class="ll-text">{pdf_export.render_markdown(disc)}</div>'
                )
            if rec:
                fields_html += (
                    f'<div class="ll-flabel">Recomendación</div>'
                    f'<div class="ll-text">{pdf_export.render_markdown(rec)}</div>'
                )
            sections_html += f'<div class="ll-item">{fields_html}</div>\n'

    description_html = f"<p>{html.escape(ll.description)}</p>" if ll.description else ""

    html_doc = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>{_CSS}</style>
</head>
<body>
<h1>LECCIONES APRENDIDAS</h1>
<h2 style="border:none; margin-top:2px;">{html.escape(ll.title)}</h2>
<div class="meta">Generado: {created} &bull; {_count_label(total)}</div>
{description_html}
<hr/>
{sections_html}
<div class="doc-footer">
  LECCIONES APRENDIDAS — {created}
</div>
</body>
</html>"""

    return _build_pdf(html_doc)


def generate_lessons_learned_markdown(ll: ArtifactLessonsLearned) -> str:
    grouped = _grouped_items(ll)
    total = sum(len(items) for items in grouped.values())

    lines = ["# Lecciones aprendidas", ""]
    if (ll.title or "").strip():
        lines += [f"## {ll.title.strip()}", ""]
    if (ll.description or "").strip():
        lines += [ll.description.strip(), ""]
    lines += [
        f"_Generado: {_fmt_dt(ll.created_at)} · {_count_label(total)}_",
        "",
        "---",
        "",
    ]

    for category in _CATEGORY_ORDER:
        items = grouped.get(category, [])
        if not items:
            continue
        lines += [f"## {_CATEGORY_LABELS[category]}", ""]
        for idx, item in enumerate(items, start=1):
            obs = (item.observation or "").strip()
            lines += [f"### {idx}. Observación", "", obs, ""]
            disc = (item.discussion or "").strip()
            if disc:
                lines += ["**Discusión**", "", disc, ""]
            rec = (item.recommendation or "").strip()
            if rec:
                lines += ["**Recomendación**", "", rec, ""]

    lines += ["---", "", "_Exportado desde AURA_"]
    return "\n".join(lines)
