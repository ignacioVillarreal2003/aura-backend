from django.utils.html import format_html


def count_badge(count: int):
    return format_html(
        '<span style="background-color: #417690; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
        count,
    )


def truncate_description(text: str, max_len: int = 50) -> str:
    if not text:
        return '-'
    return text[:max_len] + '...' if len(text) > max_len else text
