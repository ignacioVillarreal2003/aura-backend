import html
import logging

from core.export import pdf_export
from apps.artifact_document_action.exceptions import DocumentActionExportException
from apps.artifact_document_action.models import ArtifactDocumentAction

logger = logging.getLogger(__name__)

_CSS = pdf_export.DOC_BASE_CSS + """
h2 { font-size: 11pt; margin: 12px 0 4px 0; font-family: Courier, monospace; border-bottom: 1px solid #cccccc; }
p { white-space: pre-wrap; }
"""


def _fmt_dt(dt) -> str:
    return pdf_export.fmt_dt(dt)


def _build_pdf(html_content: str) -> bytes:
    return pdf_export.build_pdf(html_content, exc_factory=DocumentActionExportException, label="document-action")


def generate_document_action_pdf(obj: ArtifactDocumentAction) -> bytes:
    created = html.escape(_fmt_dt(obj.created_at))
    action_label = f" ({html.escape(obj.action)})" if obj.action else ""
    html_doc = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>{_CSS}</style>
</head>
<body>
<div class="doc-header">
  <div class="classification">ACCIÓN SOBRE DOCUMENTO{action_label}</div>
</div>
<h1>{html.escape(obj.title)}</h1>
<div class="meta">Generado: {created}</div>
<h2>Instrucción</h2>
<p>{html.escape(obj.instruction)}</p>
<h2>Resultado</h2>
<p>{html.escape(obj.result)}</p>
<div class="doc-footer">
  ACCIÓN SOBRE DOCUMENTO — {created}
</div>
</body>
</html>"""
    return _build_pdf(html_doc)


def generate_document_action_markdown(obj: ArtifactDocumentAction) -> str:
    action_label = f" ({obj.action})" if obj.action else ""
    lines = [
        f"# ACCIÓN SOBRE DOCUMENTO{action_label}",
        "",
        f"**{obj.title}**",
        "",
        f"*Generado: {_fmt_dt(obj.created_at)}*",
        "",
        "---",
        "",
        "## Instrucción",
        "",
        obj.instruction.strip(),
        "",
        "## Resultado",
        "",
        obj.result.strip(),
        "",
        "---",
        "*Acción sobre documento exportada desde AURA*",
    ]
    return "\n".join(lines)
