import pytest

pytest.importorskip("tiktoken")

from app.application.processors.text_splitters.constants.text_splitter_type import TextSplitterType
from app.application.processors.text_splitters.exceptions.text_splitter_exception import TextSplitterExecutionException
from app.application.processors.text_splitters.instances.recursive_text_splitter import RecursiveTextSplitter
from app.application.processors.text_splitters.text_splitter_settings import TextSplitterSettings


def _settings() -> TextSplitterSettings:
    return TextSplitterSettings(
        active_type=TextSplitterType.recursive,
        recursive_split_size=80,
        recursive_split_overlap=10,
        markdown_processor_split_size=512,
        markdown_processor_split_overlap=50,
    )


def test_split_empty_returns_empty_list() -> None:
    splitter = RecursiveTextSplitter(_settings())
    assert splitter.split_text("") == []
    assert splitter.split_text("   \n") == []


def test_split_produces_multiple_chunks() -> None:
    splitter = RecursiveTextSplitter(_settings())
    text = "word " * 200
    chunks = splitter.split_text(text)
    assert len(chunks) >= 2
    assert all(c.strip() for c in chunks)


def test_split_exceeds_max_text_length_raises() -> None:
    settings = TextSplitterSettings(
        active_type=TextSplitterType.recursive,
        max_text_length=50,
        recursive_split_size=80,
        recursive_split_overlap=10,
        markdown_processor_split_size=512,
        markdown_processor_split_overlap=50,
    )
    splitter = RecursiveTextSplitter(settings)
    with pytest.raises(TextSplitterExecutionException):
        splitter.split_text("x" * 51)


def test_split_single_short_string_one_chunk() -> None:
    splitter = RecursiveTextSplitter(_settings())
    chunks = splitter.split_text("hello")
    assert len(chunks) == 1
    assert chunks[0] == "hello"


def test_split_alternate_chunk_size_overlap() -> None:
    settings = TextSplitterSettings(
        active_type=TextSplitterType.recursive,
        recursive_split_size=256,
        recursive_split_overlap=30,
        markdown_processor_split_size=512,
        markdown_processor_split_overlap=50,
    )
    splitter = RecursiveTextSplitter(settings)
    text = "segment " * 400
    chunks = splitter.split_text(text)
    assert len(chunks) >= 2
    assert all(c.strip() for c in chunks)
