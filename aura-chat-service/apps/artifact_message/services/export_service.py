import html
import logging
from django.utils import timezone

from core.export import pdf_export
from apps.chat.models.chat import Chat
from apps.artifact_message.exceptions import PDFGenerationException
from apps.artifact_message.models import ArtifactMessage

logger = logging.getLogger(__name__)

_CSS = pdf_export.DOC_BASE_CSS + """
.msg { margin: 0 0 12px; }
.msg-sender {
    font-size: 8pt;
    font-weight: bold;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: #555555;
    font-family: Helvetica, Arial, sans-serif;
    margin: 12px 0 1px;
}
.msg-ts {
    font-size: 7pt;
    color: #999999;
    font-family: Helvetica, Arial, sans-serif;
    margin: 0 0 3px;
}
.msg-body { font-size: 8.5pt; color: #444444; }
.msg-body h2 { font-size: 11pt; margin: 14px 0 4px; font-family: Courier, monospace; color: #111111; }
.msg-body h3 { font-size: 9.5pt; margin: 10px 0 3px; font-family: Courier, monospace; color: #111111; }
.msg-body p { margin: 0 0 5px; }
.msg-body ul, .msg-body ol { margin: 3px 0 6px; padding-left: 18px; }
.msg-body li { margin: 1px 0; }
.msg-body pre {
    background-color: #F5F5F5;
    padding: 5px 7px;
    font-size: 8pt;
    font-family: Courier, monospace;
    white-space: pre-wrap;
    word-wrap: break-word;
}
.msg-body code { background-color: #F0F0F0; font-family: Courier, monospace; font-size: 8pt; padding: 0 3px; }
.msg-body table { border-collapse: collapse; margin: 6px 0; width: 100%; }
.msg-body th, .msg-body td { border: 1px solid #cccccc; padding: 3px 6px; font-size: 8pt; text-align: left; }
.msg-body strong { color: #111111; }
"""


def _render_markdown(text: str) -> str:
    return pdf_export.render_markdown(text)


def _fmt_dt(dt) -> str:
    return pdf_export.fmt_dt(dt)


def _count_label(count: int) -> str:
    return f"{count} {'mensaje' if count == 1 else 'mensajes'}"


def _sender_label(message: ArtifactMessage) -> str:
    return "IA" if message.sender_type == ArtifactMessage.SenderType.ASSISTANT else "Usuario"


def _build_pdf(html_content: str) -> bytes:
    return pdf_export.build_pdf(html_content, exc_factory=PDFGenerationException, label="message")


def _message_block(message: ArtifactMessage) -> str:
    sender = _sender_label(message)
    ts = html.escape(_fmt_dt(message.created_at))
    content_html = _render_markdown(message.message)
    return (
        f'<div class="msg">'
        f'<div class="msg-sender">{sender}</div>'
        f'<div class="msg-ts">{ts}</div>'
        f'<div class="msg-body">{content_html}</div>'
        f'</div>'
    )


def generate_chat_pdf(chat: Chat, messages: list[ArtifactMessage]) -> bytes:
    chat_name = html.escape(chat.name)
    created = html.escape(_fmt_dt(timezone.now()))

    blocks = [_message_block(msg) for msg in messages]
    body = "\n".join(blocks) if blocks else '<p><em>Sin mensajes en este chat.</em></p>'

    html_doc = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>{_CSS}</style>
</head>
<body>
<h1>CONVERSACIÓN</h1>
<h2 style="border:none; margin-top:2px;">{chat_name}</h2>
<div class="meta">Generado: {created} &bull; {_count_label(len(messages))}</div>
<hr/>
{body}
<div class="doc-footer">
  CONVERSACIÓN — {created}
</div>
</body>
</html>"""

    return _build_pdf(html_doc)


def generate_message_pdf(chat: Chat, message: ArtifactMessage) -> bytes:
    chat_name = html.escape(chat.name)
    created = html.escape(_fmt_dt(timezone.now()))
    sender = _sender_label(message)

    html_doc = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>{_CSS}</style>
</head>
<body>
<h1>MENSAJE</h1>
<h2 style="border:none; margin-top:2px;">{chat_name}</h2>
<div class="meta">Generado: {created} &bull; {sender}</div>
<hr/>
{_message_block(message)}
<div class="doc-footer">
  MENSAJE — {created}
</div>
</body>
</html>"""

    return _build_pdf(html_doc)


def generate_chat_markdown(chat: Chat, messages: list[ArtifactMessage]) -> str:
    lines = ["# Conversación", ""]
    if (chat.name or "").strip():
        lines += [f"## {chat.name.strip()}", ""]
    lines += [
        f"_Generado: {_fmt_dt(timezone.now())} · {_count_label(len(messages))}_",
        "",
        "---",
        "",
    ]

    for msg in messages:
        lines += [
            f"**{_sender_label(msg)}** — {_fmt_dt(msg.created_at)}",
            "",
            msg.message,
            "",
            "---",
            "",
        ]

    lines.append("_Exportado desde AURA_")
    return "\n".join(lines)


def generate_message_markdown(chat: Chat, message: ArtifactMessage) -> str:
    lines = ["# Mensaje", ""]
    if (chat.name or "").strip():
        lines += [f"## {chat.name.strip()}", ""]
    lines += [
        f"_Generado: {_fmt_dt(message.created_at)} · {_sender_label(message)}_",
        "",
        "---",
        "",
        message.message,
        "",
        "---",
        "",
        "_Exportado desde AURA_",
    ]
    return "\n".join(lines)
