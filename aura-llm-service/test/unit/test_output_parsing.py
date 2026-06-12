from app.application.services.generation_shared.output_parsing import clean_text, fallback_lines


class TestCleanText:
    def test_strips_and_truncates(self):
        assert clean_text("  hola mundo  ", 4) == "hola"

    def test_none_returns_empty(self):
        assert clean_text(None, 10) == ""

    def test_non_string_is_coerced(self):
        assert clean_text(42, 10) == "42"


class TestFallbackLines:
    def test_strips_bullets_and_numbering(self):
        raw = "• primera línea\n- segunda línea\n3) tercera línea"
        assert fallback_lines(raw) == ["primera línea", "segunda línea", "tercera línea"]

    def test_skips_blank_lines(self):
        raw = "uno\n\n   \ndos"
        assert fallback_lines(raw) == ["uno", "dos"]

    def test_line_made_only_of_bullet_chars_is_dropped(self):
        assert fallback_lines("---\nreal") == ["real"]
