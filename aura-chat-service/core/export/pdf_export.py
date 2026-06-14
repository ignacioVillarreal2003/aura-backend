import concurrent.futures
import datetime
import io
import logging
import re
from collections.abc import Callable

import markdown as md_lib
from xhtml2pdf import pisa

logger = logging.getLogger(__name__)

PDF_TIMEOUT_SECONDS = 30

# Shared CSS for the "classified document" style artifact exports (everything from
# the page setup through the H1). Each artifact appends its own extra rules.
DOC_BASE_CSS = """
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
"""

_DANGEROUS_TAGS_RE = re.compile(
    r"<\s*/?\s*(script|style|iframe|object|embed|form|input|button|textarea|img|link|meta|base)\b[^>]*>",
    re.IGNORECASE,
)


def safe_link_callback(uri: str, rel: str) -> str:
    return ""


def render_markdown(text: str) -> str:
    raw_html = md_lib.markdown(text, extensions=["fenced_code", "tables", "nl2br"])
    return _DANGEROUS_TAGS_RE.sub("", raw_html)


def fmt_dt(dt) -> str:
    if dt is None:
        return ""
    utc = dt.astimezone(datetime.timezone.utc) if dt.tzinfo else dt
    return utc.strftime("%Y-%m-%d %H:%M UTC")


def build_pdf(html_content: str, *, exc_factory: Callable[[], Exception], label: str) -> bytes:
    """Render html_content to PDF bytes off the event loop.

    exc_factory builds the artifact-specific export exception; label is used only
    in log messages (e.g. "checklist", "report").
    """

    def _sync() -> bytes:
        buf = io.BytesIO()
        result = pisa.CreatePDF(
            io.StringIO(html_content), dest=buf, encoding="utf-8", link_callback=safe_link_callback,
        )
        if result.err:
            logger.error("xhtml2pdf reported %d error(s) during %s PDF generation", result.err, label)
            raise exc_factory()
        return buf.getvalue()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_sync)
        try:
            return future.result(timeout=PDF_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            logger.error("%s PDF generation timed out after %ds", label, PDF_TIMEOUT_SECONDS)
            raise exc_factory()
