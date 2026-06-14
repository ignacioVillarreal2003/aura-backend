import html
import logging
from django.utils import timezone

from core.export import pdf_export
from apps.chat.models.chat import Chat
from apps.artifact_message.exceptions import PDFGenerationException
from apps.artifact_message.models import ArtifactMessage

logger = logging.getLogger(__name__)

_CSS = """
@page {
    size: A4;
    margin: 2cm;
}
body {
    font-family: Helvetica, Arial, sans-serif;
    font-size: 10pt;
    color: #222222;
    line-height: 1.5;
}
h1 {
    font-size: 16pt;
    color: #111111;
    margin-bottom: 4px;
}
.meta {
    font-size: 8pt;
    color: #888888;
    margin-bottom: 20px;
}
.bubble {
    margin-bottom: 12px;
    padding: 8px 12px;
    border-left: 4px solid #cccccc;
}
.bubble-user {
    background-color: #EEF2FF;
    border-left-color: #4F6EF7;
}
.bubble-system {
    background-color: #F0FDF4;
    border-left-color: #22C55E;
}
.sender {
    font-size: 8pt;
    font-weight: bold;
    color: #555555;
    text-transform: uppercase;
    margin-bottom: 4px;
}
.ts {
    font-size: 7pt;
    color: #aaaaaa;
    margin-top: 6px;
}
p { margin: 3px 0; }
pre {
    background-color: #F5F5F5;
    padding: 6px 8px;
    font-size: 8pt;
    font-family: Courier, monospace;
}
code {
    background-color: #F0F0F0;
    font-family: Courier, monospace;
    font-size: 8pt;
    padding: 1px 3px;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 8px 0;
}
th, td {
    border: 1px solid #dddddd;
    padding: 4px 8px;
    font-size: 9pt;
    text-align: left;
}
th {
    background-color: #F0F0F0;
    font-weight: bold;
}
ul, ol { margin: 4px 0; padding-left: 20px; }
li { margin: 2px 0; }
blockquote {
    border-left: 3px solid #cccccc;
    margin: 4px 0;
    padding-left: 8px;
    color: #666666;
}
"""

def _render_markdown(text: str) -> str:
    return pdf_export.render_markdown(text)


def _fmt_dt(dt) -> str:
    return pdf_export.fmt_dt(dt)


def _build_pdf(html_content: str) -> bytes:
    return pdf_export.build_pdf(html_content, exc_factory=PDFGenerationException, label="message")


def generate_chat_pdf(chat: Chat, messages: list[ArtifactMessage]) -> bytes:
    chat_name = html.escape(chat.name)
    export_date = html.escape(_fmt_dt(timezone.now()))

    rows: list[str] = []
    for msg in messages:
        is_system = msg.sender_type == ArtifactMessage.SenderType.ASSISTANT
        css_class = "bubble-system" if is_system else "bubble-user"
        sender_label = "AI" if is_system else "User"
        content_html = _render_markdown(msg.message)
        ts = html.escape(_fmt_dt(msg.created_at))
        rows.append(
            f'<div class="bubble {css_class}">'
            f'<div class="sender">{sender_label}</div>'
            f"{content_html}"
            f'<div class="ts">{ts}</div>'
            f"</div>"
        )

    count = len(rows)
    body = "\n".join(rows) if rows else "<p><em>No messages in this chat.</em></p>"

    html_doc = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>{_CSS}</style>
</head>
<body>
<h1>{chat_name}</h1>
<div class="meta">Exported on {export_date} &bull; {count} message(s)</div>
{body}
</body>
</html>"""

    return _build_pdf(html_doc)


def generate_chat_markdown(chat: Chat, messages: list[ArtifactMessage]) -> str:
    lines = [
        f"# {chat.name}",
        "",
        f"*Exported on {_fmt_dt(timezone.now())} — {len(messages)} message(s)*",
        "",
        "---",
        "",
    ]
    for msg in messages:
        is_system = msg.sender_type == ArtifactMessage.SenderType.ASSISTANT
        sender = "**AI**" if is_system else "**User**"
        lines.append(f"{sender} — {_fmt_dt(msg.created_at)}")
        lines.append("")
        lines.append(msg.message)
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def generate_message_markdown(chat: Chat, message: ArtifactMessage) -> str:
    is_system = message.sender_type == ArtifactMessage.SenderType.ASSISTANT
    sender = "**AI**" if is_system else "**User**"
    lines = [
        f"# {chat.name}",
        "",
        f"*{sender} — {_fmt_dt(message.created_at)}*",
        "",
        message.message,
        "",
    ]
    return "\n".join(lines)


def generate_message_pdf(chat: Chat, message: ArtifactMessage) -> bytes:
    chat_name = html.escape(chat.name)
    export_date = html.escape(_fmt_dt(timezone.now()))
    is_system = message.sender_type == ArtifactMessage.SenderType.ASSISTANT
    css_class = "bubble-system" if is_system else "bubble-user"
    sender_label = "AI" if is_system else "User"
    content_html = _render_markdown(message.message)
    msg_dt = html.escape(_fmt_dt(message.created_at))

    html_doc = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>{_CSS}</style>
</head>
<body>
<h1>{chat_name}</h1>
<div class="meta">{sender_label} &bull; {msg_dt} &bull; Exported on {export_date}</div>
<div class="bubble {css_class}">
{content_html}
</div>
</body>
</html>"""

    return _build_pdf(html_doc)
