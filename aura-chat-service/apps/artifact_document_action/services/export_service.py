import html
import logging

from core.export import pdf_export
from apps.artifact_document_action.exceptions import DocumentActionExportException
from apps.artifact_document_action.models import ArtifactDocumentAction

logger = logging.getLogger(__name__)

_CSS = pdf_export.DOC_BASE_CSS + """
.da-sec { font-size: 9pt; font-weight: bold; color: #111111; font-family: Helvetica, Arial, sans-serif; margin: 16px 0 3px; }
.da-instruction { font-size: 8.5pt; color: #444444; white-space: pre-wrap; margin: 0 0 4px; }
.da-body { font-size: 8.5pt; color: #444444; }
.da-body h2 { font-size: 11pt; margin: 14px 0 4px; font-family: Courier, monospace; color: #111111; }
.da-body h3 { font-size: 9.5pt; margin: 10px 0 3px; font-family: Courier, monospace; color: #111111; }
.da-body p { margin: 0 0 5px; }
.da-body ul, .da-body ol { margin: 3px 0 6px; padding-left: 18px; }
.da-body li { margin: 1px 0; }
.da-body table { border-collapse: collapse; margin: 6px 0; width: 100%; }
.da-body th, .da-body td { border: 1px solid #cccccc; padding: 3px 6px; font-size: 8pt; text-align: left; }
.da-body strong { color: #111111; }
"""


def _fmt_dt(dt) -> str:
    return pdf_export.fmt_dt(dt)


def _build_pdf(html_content: str) -> bytes:
    return pdf_export.build_pdf(html_content, exc_factory=DocumentActionExportException, label="document-action")


def generate_document_action_pdf(obj: ArtifactDocumentAction) -> bytes:
    created = html.escape(_fmt_dt(obj.created_at))
    action_label = f" ({html.escape(obj.action)})" if obj.action else ""
    description_html = f"<p>{html.escape(obj.description)}</p>" if obj.description else ""
    instruction_html = (
        f'<div class="da-sec">Instrucción</div><div class="da-instruction">{html.escape(obj.instruction)}</div>'
        if obj.instruction.strip() else ""
    )
    body_html = f'<div class="da-body">{pdf_export.render_markdown(obj.result.strip())}</div>' if obj.result.strip() else ""

    html_doc = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>{_CSS}</style>
</head>
<body>
<h1>ACCIÓN SOBRE DOCUMENTO{action_label}</h1>
<h2 style="border:none; margin-top:2px;">{html.escape(obj.title)}</h2>
<div class="meta">Generado: {created}</div>
{description_html}
<hr/>
{instruction_html}
{body_html}
<div class="doc-footer">
  ACCIÓN SOBRE DOCUMENTO — {created}
</div>
</body>
</html>"""
    return _build_pdf(html_doc)


def generate_document_action_markdown(obj: ArtifactDocumentAction) -> str:
    action_label = f" ({obj.action})" if obj.action else ""
    lines = [f"# Acción sobre documento{action_label}", ""]
    if (obj.title or "").strip():
        lines += [f"## {obj.title.strip()}", ""]
    if (obj.description or "").strip():
        lines += [obj.description.strip(), ""]
    lines += [
        f"_Generado: {_fmt_dt(obj.created_at)}_",
        "",
        "---",
        "",
    ]
    if (obj.instruction or "").strip():
        lines += ["## Instrucción", "", obj.instruction.strip(), ""]
    lines += ["## Resultado", "", obj.result.strip(), "", "---", "", "_Exportado desde AURA_"]
    return "\n".join(lines)
