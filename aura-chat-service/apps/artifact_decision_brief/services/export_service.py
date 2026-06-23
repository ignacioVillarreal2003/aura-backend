import html
import logging

from core.export import pdf_export
from apps.artifact_decision_brief.exceptions import DecisionBriefExportException
from apps.artifact_decision_brief.models import ArtifactDecisionBrief

logger = logging.getLogger(__name__)

_CSS = pdf_export.DOC_BASE_CSS + """
.db-sec {
    font-size: 9pt;
    font-weight: bold;
    color: #111111;
    font-family: Helvetica, Arial, sans-serif;
    margin: 16px 0 3px;
}
.db-text { font-size: 8.5pt; color: #444444; margin: 0 0 4px; }
.db-text p { margin: 0 0 4px; }
.db-text p:last-child { margin-bottom: 0; }
.db-text ul, .db-text ol { margin: 2px 0 4px; padding-left: 16px; }
.db-text li { margin: 1px 0; }
.db-opt { margin: 6px 0 10px; }
.db-opt-title { font-size: 9pt; font-weight: bold; color: #111111; margin: 0 0 2px; }
.db-flabel {
    font-size: 7.5pt;
    font-weight: bold;
    color: #888888;
    font-family: Helvetica, Arial, sans-serif;
    margin: 4px 0 1px;
}
"""


def _fmt_dt(dt) -> str:
    return pdf_export.fmt_dt(dt)


def _count_label(count: int) -> str:
    return f"{count} {'opción' if count == 1 else 'opciones'}"


def _build_pdf(html_content: str) -> bytes:
    return pdf_export.build_pdf(html_content, exc_factory=DecisionBriefExportException, label="decision-brief")


def _prose_section(label: str, body: str) -> str:
    body = (body or "").strip()
    if not body:
        return ""
    return (
        f'<div class="db-sec">{html.escape(label)}</div>'
        f'<div class="db-text">{pdf_export.render_markdown(body)}</div>\n'
    )


def generate_decision_brief_pdf(brief: ArtifactDecisionBrief) -> bytes:
    options = list(brief.options.all())
    created = html.escape(_fmt_dt(brief.created_at))

    options_html = ""
    if options:
        options_html += '<div class="db-sec">Opciones</div>\n'
        for idx, opt in enumerate(options, start=1):
            star = " &#9733; Recomendada" if opt.is_recommended else ""
            options_html += (
                f'<div class="db-opt">'
                f'<div class="db-opt-title">{idx}. {html.escape(opt.title)}{star}</div>'
            )
            if (opt.pros or "").strip():
                options_html += (
                    f'<div class="db-flabel">A favor</div>'
                    f'<div class="db-text">{pdf_export.render_markdown(opt.pros.strip())}</div>'
                )
            if (opt.cons or "").strip():
                options_html += (
                    f'<div class="db-flabel">En contra</div>'
                    f'<div class="db-text">{pdf_export.render_markdown(opt.cons.strip())}</div>'
                )
            options_html += "</div>\n"

    description_html = f"<p>{html.escape(brief.description)}</p>" if brief.description else ""

    html_doc = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>{_CSS}</style>
</head>
<body>
<h1>BRIEF DE DECISIÓN</h1>
<h2 style="border:none; margin-top:2px;">{html.escape(brief.title)}</h2>
<div class="meta">Generado: {created} &bull; {_count_label(len(options))}</div>
{description_html}
<hr/>
{_prose_section("Contexto", brief.context)}
{options_html}
{_prose_section("Riesgos", brief.risks)}
{_prose_section("Recomendación final", brief.recommendation)}
<div class="doc-footer">
  BRIEF DE DECISIÓN — {created}
</div>
</body>
</html>"""

    return _build_pdf(html_doc)


def generate_decision_brief_markdown(brief: ArtifactDecisionBrief) -> str:
    options = list(brief.options.all())

    lines = ["# Brief de decisión", ""]
    if (brief.title or "").strip():
        lines += [f"## {brief.title.strip()}", ""]
    if (brief.description or "").strip():
        lines += [brief.description.strip(), ""]
    lines += [
        f"_Generado: {_fmt_dt(brief.created_at)} · {_count_label(len(options))}_",
        "",
        "---",
        "",
    ]

    if (brief.context or "").strip():
        lines += ["## Contexto", "", brief.context.strip(), ""]

    if options:
        lines += ["## Opciones", ""]
        for idx, opt in enumerate(options, start=1):
            star = " ⭐ Recomendada" if opt.is_recommended else ""
            lines += [f"### {idx}. {opt.title}{star}", ""]
            if (opt.pros or "").strip():
                lines += ["**A favor**", "", opt.pros.strip(), ""]
            if (opt.cons or "").strip():
                lines += ["**En contra**", "", opt.cons.strip(), ""]

    if (brief.risks or "").strip():
        lines += ["## Riesgos", "", brief.risks.strip(), ""]
    if (brief.recommendation or "").strip():
        lines += ["## Recomendación final", "", brief.recommendation.strip(), ""]

    lines += ["---", "", "_Exportado desde AURA_"]
    return "\n".join(lines)
