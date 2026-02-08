from enum import Enum


class EmbedderType(str, Enum):
    huggingface = "huggingface"
    ollama = "ollama",
    sentence_transformer = "sentence_transformer",
    spacy = "spacy"
