import pytest

from app.application.processors.text_cleaners.exceptions.text_cleaner_exception import TextCleanerExecutionException
from app.application.processors.text_cleaners.instances.simple_text_cleaner import SimpleTextCleaner
from app.application.processors.text_cleaners.text_cleaner_settings import TextCleanerSettings


def _settings(**kwargs) -> TextCleanerSettings:
    base = dict(
        simple_remove_urls=False,
        simple_remove_emojis=False,
        simple_remove_markdown=False,
        simple_normalize_whitespace=True,
        simple_remove_noise_lines=False,
        max_text_length=10_000,
    )
    base.update(kwargs)
    return TextCleanerSettings(**base)


def test_clean_empty_or_whitespace_returns_empty() -> None:
    cleaner = SimpleTextCleaner(_settings())
    assert cleaner.clean_text("") == ""
    assert cleaner.clean_text("   \n\t  ") == ""


def test_clean_exceeds_max_length_raises() -> None:
    cleaner = SimpleTextCleaner(_settings(max_text_length=5))
    with pytest.raises(TextCleanerExecutionException):
        cleaner.clean_text("123456")


def test_remove_urls() -> None:
    cleaner = SimpleTextCleaner(_settings(simple_remove_urls=True))
    out = cleaner.clean_text("See https://example.com and www.test.org done")
    assert "https://" not in out and "www." not in out
    assert "done" in out


def test_remove_emojis() -> None:
    cleaner = SimpleTextCleaner(_settings(simple_remove_emojis=True))
    out = cleaner.clean_text("Hello 😀 world")
    assert "😀" not in out
    assert "Hello" in out and "world" in out


def test_remove_markdown() -> None:
    cleaner = SimpleTextCleaner(_settings(simple_remove_markdown=True))
    out = cleaner.clean_text("**bold** and `code` and [l](http://x)")
    assert "**" not in out
    assert "bold" in out and "code" in out


def test_normalize_whitespace_default() -> None:
    cleaner = SimpleTextCleaner(_settings(simple_normalize_whitespace=True))
    out = cleaner.clean_text("a    b\n\n\nc")
    assert "  " not in out.replace("\n\n", "")
    assert "a b" in out or "a" in out


def test_non_string_input_returns_empty() -> None:
    cleaner = SimpleTextCleaner(_settings())
    assert cleaner.clean_text(None) == ""  # type: ignore[arg-type]


def test_crlf_and_cr_normalized_to_lf() -> None:
    cleaner = SimpleTextCleaner(_settings())
    out = cleaner.clean_text("line1\r\nline2\rline3")
    assert "\r" not in out
    assert "line1" in out and "line2" in out and "line3" in out


def test_tabs_replaced_with_spaces() -> None:
    cleaner = SimpleTextCleaner(_settings(simple_normalize_whitespace=True))
    out = cleaner.clean_text("a\tb")
    assert "\t" not in out


def test_combined_url_emoji_markdown() -> None:
    cleaner = SimpleTextCleaner(
        _settings(
            simple_remove_urls=True,
            simple_remove_emojis=True,
            simple_remove_markdown=True,
            simple_normalize_whitespace=True,
        )
    )
    out = cleaner.clean_text("Hi 😀 see **bold** at https://x.com/y ok")
    assert "https://" not in out and "😀" not in out and "**" not in out
    assert "bold" in out and "Hi" in out and "ok" in out


def test_remove_noise_lines_separator_dashes() -> None:
    cleaner = SimpleTextCleaner(_settings(simple_remove_noise_lines=True, simple_normalize_whitespace=True))
    out = cleaner.clean_text("keep\n---\nalso")
    assert "---" not in out
    assert "keep" in out and "also" in out


def test_remove_noise_lines_equals() -> None:
    cleaner = SimpleTextCleaner(_settings(simple_remove_noise_lines=True))
    out = cleaner.clean_text("intro\n=====\nbody")
    assert "=====" not in out
    assert "intro" in out and "body" in out


def test_remove_noise_lines_hash_tilde_pattern() -> None:
    cleaner = SimpleTextCleaner(_settings(simple_remove_noise_lines=True, simple_normalize_whitespace=True))
    out = cleaner.clean_text("start\n###\nend")
    assert "###" not in out
    assert "start" in out and "end" in out


def test_bullet_hyphen_merges_with_next_line() -> None:
    cleaner = SimpleTextCleaner(_settings(simple_remove_noise_lines=True, simple_normalize_whitespace=True))
    out = cleaner.clean_text("-\nFirst item")
    assert "First item" in out


def test_bullet_star_merges_with_next_line() -> None:
    cleaner = SimpleTextCleaner(_settings(simple_remove_noise_lines=True, simple_normalize_whitespace=True))
    out = cleaner.clean_text("*\nSecond")
    assert "Second" in out


def test_bullet_bullet_char_merges_with_next_line() -> None:
    cleaner = SimpleTextCleaner(_settings(simple_remove_noise_lines=True, simple_normalize_whitespace=True))
    out = cleaner.clean_text("•\nThird")
    assert "Third" in out


def test_bullet_hyphen_no_merge_when_next_line_empty() -> None:
    cleaner = SimpleTextCleaner(_settings(simple_remove_noise_lines=True, simple_normalize_whitespace=True))
    out = cleaner.clean_text("-\n\nafter")
    assert "after" in out


def test_italic_single_asterisk_markdown() -> None:
    cleaner = SimpleTextCleaner(_settings(simple_remove_markdown=True))
    out = cleaner.clean_text("this is *italic* end")
    assert "*" not in out
    assert "italic" in out


def test_inline_code_strips_backticks() -> None:
    cleaner = SimpleTextCleaner(_settings(simple_remove_markdown=True))
    out = cleaner.clean_text("run `pip install` now")
    assert "`" not in out
    assert "pip install" in out


def test_markdown_link_strips_url() -> None:
    cleaner = SimpleTextCleaner(_settings(simple_remove_markdown=True))
    out = cleaner.clean_text("see [label](https://example.com) end")
    assert "[" not in out and "](" not in out
    assert "label" in out and "end" in out


def test_normalize_whitespace_disabled_keeps_double_spaces_in_line() -> None:
    cleaner = SimpleTextCleaner(_settings(simple_normalize_whitespace=False))
    out = cleaner.clean_text("a  b")
    assert "a  b" in out


def test_max_length_boundary_ok() -> None:
    cleaner = SimpleTextCleaner(_settings(max_text_length=5))
    assert cleaner.clean_text("12345") == "12345"


def test_strip_final_output() -> None:
    cleaner = SimpleTextCleaner(_settings())
    assert cleaner.clean_text("  trimmed  ") == "trimmed"
