import concurrent.futures
import datetime
import html
import io
import logging
from xhtml2pdf import pisa

from apps.artifact.models.artifact import Artifact
from apps.artifact_quiz.exceptions import QuizExportException
from apps.artifact_quiz.models import ArtifactQuiz, ArtifactQuizQuestion

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
.q-block { margin: 8px 0; padding: 2px 0; }
.q-text { font-size: 9.5pt; font-weight: bold; }
.q-opt { margin: 1px 0 1px 14px; font-size: 9pt; }
.q-opt.correct { font-weight: bold; }
.q-expl { font-size: 8pt; color: #555555; margin: 2px 0 0 14px; font-style: italic; }
"""

_TYPE_LABELS = {
    ArtifactQuizQuestion.Kind.SINGLE: "Opción única",
    ArtifactQuizQuestion.Kind.MULTIPLE: "Opción múltiple",
    ArtifactQuizQuestion.Kind.BOOLEAN: "Verdadero/Falso"
}


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
        logger.error("xhtml2pdf reported %d error(s) during quiz PDF generation", result.err)
        raise QuizExportException()
    return buf.getvalue()


def _build_pdf(html_content: str) -> bytes:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_build_pdf_sync, html_content)
        try:
            return future.result(timeout=_PDF_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            logger.error("ArtifactQuiz PDF generation timed out after %ds", _PDF_TIMEOUT_SECONDS)
            raise QuizExportException()


def generate_quiz_pdf(quiz: ArtifactQuiz, *, with_answers: bool = True) -> bytes:
    questions = list(quiz.questions.all())
    mode_label = "Con documentos de contexto" if quiz.artifact.mode == Artifact.Mode.RAG else "Directo"
    created = html.escape(_fmt_dt(quiz.created_at))
    pass_label = f"{quiz.pass_score}%" if quiz.pass_score is not None else "—"

    questions_html = ""
    for idx, question in enumerate(questions, start=1):
        type_label = html.escape(_TYPE_LABELS.get(question.kind, question.kind))
        q_text = html.escape(question.text)
        questions_html += f'<div class="q-block"><div class="q-text">{idx}. {q_text} <span style="font-weight:normal; font-size:8pt; color:#777;">({type_label})</span></div>\n'
        for opt in question.options.all():
            mark = "&#9745;" if (with_answers and opt.is_correct) else "&#9744;"
            cls = "q-opt correct" if (with_answers and opt.is_correct) else "q-opt"
            questions_html += f'<div class="{cls}">{mark} {html.escape(opt.text)}</div>\n'
        if with_answers and question.explanation.strip():
            questions_html += f'<div class="q-expl">{html.escape(question.explanation)}</div>\n'
        questions_html += "</div>\n"

    instructions_html = f"<p>{html.escape(quiz.instructions)}</p>" if quiz.instructions else ""

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
<h1>CUESTIONARIO DE EVALUACIÓN</h1>
<h2 style="border:none; margin-top:2px;">{html.escape(quiz.title)}</h2>
<div class="meta">Generado: {created} &bull; Modo: {mode_label} &bull; Puntaje mínimo: {pass_label} &bull; {len(questions)} preguntas</div>
{instructions_html}
<hr/>
{questions_html}
<div class="doc-footer">
  CLASIFICACIÓN SEGÚN CONTENIDO — CUESTIONARIO — {created}
</div>
</body>
</html>"""

    return _build_pdf(html_doc)


def generate_quiz_markdown(quiz: ArtifactQuiz, *, with_answers: bool = True) -> str:
    questions = list(quiz.questions.all())
    pass_label = f"{quiz.pass_score}%" if quiz.pass_score is not None else "—"

    lines = [
        "# CUESTIONARIO DE EVALUACIÓN",
        "",
        f"**{quiz.title}**",
        "",
        f"*Generado: {_fmt_dt(quiz.created_at)}*",
        "",
        f"*Puntaje mínimo: {pass_label}*",
        "",
    ]
    if (quiz.instructions or "").strip():
        lines += [quiz.instructions.strip(), ""]
    lines += ["---", ""]

    for idx, question in enumerate(questions, start=1):
        type_label = _TYPE_LABELS.get(question.kind, question.kind)
        lines.append(f"### {idx}. {question.text} _({type_label})_")
        for opt in question.options.all():
            checkbox = "[x]" if (with_answers and opt.is_correct) else "[ ]"
            lines.append(f"- {checkbox} {opt.text}")
        if with_answers and question.explanation.strip():
            lines.append(f"  > {question.explanation}")
        lines.append("")

    lines += ["---", "*Cuestionario exportado desde AURA*"]
    return "\n".join(lines)
