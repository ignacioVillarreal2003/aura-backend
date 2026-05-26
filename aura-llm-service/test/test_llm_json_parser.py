"""
Unit tests for app.application.utils.llm_json_parser.parse_json_object.
"""
import json
import pytest
from app.application.utils.llm_json_parser import parse_json_object


class TestParseJsonObject:
    def test_parses_plain_json_string(self):
        result = parse_json_object('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parses_nested_object(self):
        result = parse_json_object('{"a": {"b": 1}}')
        assert result["a"]["b"] == 1

    def test_parses_json_with_leading_and_trailing_whitespace(self):
        result = parse_json_object('   {"key": "value"}   ')
        assert result == {"key": "value"}

    def test_parses_json_wrapped_in_plain_backtick_block(self):
        text = "```\n{\"key\": \"value\"}\n```"
        result = parse_json_object(text)
        assert result == {"key": "value"}

    def test_parses_json_wrapped_in_json_code_block(self):
        text = "```json\n{\"key\": \"value\"}\n```"
        result = parse_json_object(text)
        assert result == {"key": "value"}

    def test_parses_json_embedded_in_surrounding_text(self):
        text = 'Here is the result: {"type": "informe", "category": "Legal"} as requested.'
        result = parse_json_object(text)
        assert result["type"] == "informe"
        assert result["category"] == "Legal"

    def test_raises_json_decode_error_for_invalid_json(self):
        with pytest.raises(json.JSONDecodeError):
            parse_json_object("this is not json at all")

    def test_raises_json_decode_error_when_no_braces_found(self):
        with pytest.raises(json.JSONDecodeError):
            parse_json_object("just some random text")

    def test_raises_type_error_for_json_array(self):
        with pytest.raises(TypeError):
            parse_json_object('[1, 2, 3]')

    def test_raises_type_error_for_json_string_value(self):
        with pytest.raises(TypeError):
            parse_json_object('"just a string"')

    def test_returns_dict_type(self):
        result = parse_json_object('{"x": 1}')
        assert isinstance(result, dict)

    def test_parses_json_with_multiple_fields(self):
        payload = '{"type": "manual", "category": "Técnico", "confidence": 0.95}'
        result = parse_json_object(payload)
        assert result["type"] == "manual"
        assert result["category"] == "Técnico"
        assert result["confidence"] == 0.95

    def test_parses_empty_object(self):
        result = parse_json_object('{}')
        assert result == {}
