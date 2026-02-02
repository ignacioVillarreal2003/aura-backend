from enum import Enum


class EmbedderType(str, Enum):
    HUGGINGFACE = "huggingface"
    OLLAMA = "ollama",
    SENTENCE_TRANSFORMER = "sentence_transformer",
    SPACY = "spacy"
