import html
import logging

from core.export import pdf_export
from apps.artifact_quiz.exceptions import QuizExportException
from apps.artifact_quiz.models import ArtifactQuiz, ArtifactQuizQuestion

logger = logging.getLogger(__name__)

_CSS = pdf_export.DOC_BASE_CSS + """
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


def _fmt_dt(dt) -> str:
    return pdf_export.fmt_dt(dt)


def _build_pdf(html_content: str) -> bytes:
    return pdf_export.build_pdf(html_content, exc_factory=QuizExportException, label="quiz")


def generate_quiz_pdf(quiz: ArtifactQuiz, *, with_answers: bool = True) -> bytes:
    questions = list(quiz.questions.all())
    created = html.escape(_fmt_dt(quiz.created_at))
    description_html = f"<p>{html.escape(quiz.description)}</p>" if quiz.description else ""

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
<h1>CUESTIONARIO DE EVALUACIÓN</h1>
<h2 style="border:none; margin-top:2px;">{html.escape(quiz.title)}</h2>
<div class="meta">Generado: {created} &bull; {len(questions)} preguntas</div>
{description_html}
{instructions_html}
<hr/>
{questions_html}
<div class="doc-footer">
  CUESTIONARIO — {created}
</div>
</body>
</html>"""

    return _build_pdf(html_doc)


def generate_quiz_markdown(quiz: ArtifactQuiz, *, with_answers: bool = True) -> str:
    questions = list(quiz.questions.all())

    lines = ["# Cuestionario de evaluación", ""]
    if (quiz.title or "").strip():
        lines += [f"## {quiz.title.strip()}", ""]
    if (quiz.description or "").strip():
        lines += [quiz.description.strip(), ""]
    lines += [f"_Generado: {_fmt_dt(quiz.created_at)} · {len(questions)} preguntas_", ""]
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

    lines += ["---", "", "_Exportado desde AURA_"]
    return "\n".join(lines)
