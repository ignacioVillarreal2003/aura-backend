from enum import Enum


class TextSplitterType(str, Enum):
    TOKEN = "token"
    SPACY = "spacy",
    SENTENCE_TRANSFORMER = "sentence_transformer",
    SEMANTIC = "semantic"
    RECURSIVE = "recursive",
    HUGGINGFACE = "huggingface",
    CHAR_TIKTOKEN = "char_tiktoken"
    CHAR = "char"
