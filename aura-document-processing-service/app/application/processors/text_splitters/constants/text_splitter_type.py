from enum import Enum


class TextSplitterType(str, Enum):
    markdown_processor = "markdown_processor"
    huggingface = "huggingface"
    recursive = "recursive"
