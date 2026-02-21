from enum import Enum


class TextSplitterType(str, Enum):
    recursive = "recursive"


"""
token = "token"
spacy = "spacy",
sentence_transformer = "sentence_transformer",
semantic = "semantic"
recursive = "recursive",
huggingface = "huggingface",
char_tiktoken = "char_tiktoken"
char = "char"
"""
