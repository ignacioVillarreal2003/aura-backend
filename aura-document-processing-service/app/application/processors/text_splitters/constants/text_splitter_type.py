from enum import Enum


class TextSplitterType(str, Enum):
    huggingface = "huggingface"
    recursive = "recursive"
