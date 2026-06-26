import pytest

from app.infrastructure.persistence.database.repositories.fragment_repository import (
    _sanitize_bm25_search_input,
)
from app.infrastructure.persistence.database.repositories.repository_query_utils import (
    DEFAULT_IN_CLAUSE_CHUNK_SIZE,
    chunked_ids,
)



class TestChunkedIds:
    def test_empty_input_yields_nothing(self):
        assert list(chunked_ids([])) == []

    def test_dedups_preserving_first_seen_order(self):
        assert list(chunked_ids([3, 1, 3, 2, 1], chunk_size=10)) == [[3, 1, 2]]

    def test_splits_into_chunks_of_requested_size(self):
        result = list(chunked_ids([1, 2, 3, 4, 5], chunk_size=2))
        assert result == [[1, 2], [3, 4], [5]]

    def test_dedup_happens_before_chunking(self):
        result = list(chunked_ids([1, 1, 2, 2, 3, 3, 4, 4], chunk_size=2))
        assert result == [[1, 2], [3, 4]]

    def test_default_chunk_size_keeps_small_lists_in_one_chunk(self):
        ids = list(range(10))
        result = list(chunked_ids(ids))
        assert result == [ids]
        assert DEFAULT_IN_CLAUSE_CHUNK_SIZE >= 10



class TestSanitizeBm25Input:
    def test_strips_non_word_punctuation(self):
        assert _sanitize_bm25_search_input("foo & (bar) | baz", 100) == "foo bar baz"

    def test_keeps_allowed_punctuation(self):
        assert _sanitize_bm25_search_input("v1.2-beta, ok", 100) == "v1.2-beta, ok"

    def test_collapses_whitespace(self):
        assert _sanitize_bm25_search_input("foo   \t bar\n baz", 100) == "foo bar baz"

    def test_drops_non_printable_characters(self):
        assert _sanitize_bm25_search_input("foo\x00\x07bar", 100) == "foobar"

    def test_all_special_input_yields_empty_string(self):
        assert _sanitize_bm25_search_input("@#$%^*", 100) == ""

    def test_truncates_to_max_chars(self):
        assert _sanitize_bm25_search_input("abcdefghij", 4) == "abcd"

    @pytest.mark.parametrize("raw", ["", "   ", "\n\t"])
    def test_blank_inputs_return_empty(self, raw):
        assert _sanitize_bm25_search_input(raw, 100) == ""
