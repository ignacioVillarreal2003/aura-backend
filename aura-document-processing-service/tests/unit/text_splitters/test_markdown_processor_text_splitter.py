import pytest

pytest.importorskip("tiktoken")

from app.application.processors.text_splitters.constants.text_splitter_type import TextSplitterType
from app.application.processors.text_splitters.exceptions.text_splitter_exception import TextSplitterExecutionException
from app.application.processors.text_splitters.instances.markdown_processor_text_splitter import (
    MarkdownProcessorTextSplitter,
)
from app.application.processors.text_splitters.text_splitter_settings import TextSplitterSettings


def _settings() -> TextSplitterSettings:
    return TextSplitterSettings(
        active_type=TextSplitterType.markdown_processor,
        recursive_split_size=512,
        recursive_split_overlap=50,
        markdown_processor_split_size=100,
        markdown_processor_split_overlap=20,
    )


def test_split_empty_returns_empty_list() -> None:
    splitter = MarkdownProcessorTextSplitter(_settings())
    assert splitter.split_text("") == []


def test_split_whitespace_only_returns_empty_list() -> None:
    splitter = MarkdownProcessorTextSplitter(_settings())
    assert splitter.split_text("   \n") == []


def test_split_exceeds_max_text_length_raises() -> None:
    settings = TextSplitterSettings(
        active_type=TextSplitterType.markdown_processor,
        max_text_length=40,
        recursive_split_size=512,
        recursive_split_overlap=50,
        markdown_processor_split_size=100,
        markdown_processor_split_overlap=20,
    )
    splitter = MarkdownProcessorTextSplitter(settings)
    with pytest.raises(TextSplitterExecutionException):
        splitter.split_text("# H\n\n" + ("p " * 50))


def test_split_markdown_headings() -> None:
    splitter = MarkdownProcessorTextSplitter(_settings())
    text = "# A\n\n" + ("para " * 80) + "\n\n## B\n\n" + ("line " * 80)
    chunks = splitter.split_text(text)
    assert len(chunks) >= 1
    joined = "\n".join(chunks)
    assert "A" in joined or "para" in joined


def test_split_markdown_with_fence_and_list() -> None:
    splitter = MarkdownProcessorTextSplitter(_settings())
    text = (
        "# Section\n\n"
        "- item one\n"
        "- item two\n\n"
        "```python\n"
        "def foo():\n"
        "    return 1\n"
        "```\n\n"
        + ("More body " * 60)
    )
    chunks = splitter.split_text(text)
    assert len(chunks) >= 1
    joined = "\n".join(chunks)
    assert "Section" in joined or "More body" in joined or "foo" in joined
