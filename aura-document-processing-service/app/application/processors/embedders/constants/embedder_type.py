from enum import Enum


class EmbedderType(str, Enum):
    ollama = "ollama"
    huggingface = "huggingface"
