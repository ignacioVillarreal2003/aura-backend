import re


def safe_filename(title: str) -> str:
    return re.sub(r"[^\w\-]", "_", title[:60])
