from typing import Dict

from app.application.processors.text_splitters.interfaces.text_splitter_interface import TextSplitterInterface
from app.application.processors.text_splitters.token_text_splitter import TokenTextSplitter
from app.application.processors.text_splitters.spacy_text_splitter import SpacyTextSplitter
from app.application.processors.text_splitters.sentence_transformer_text_splitter import SentenceTransformerTextSplitter
from app.application.processors.text_splitters.semantic_text_splitter import SemanticTextSplitter
from app.application.processors.text_splitters.recursive_text_splitter import RecursiveTextSplitter
from app.application.processors.text_splitters.huggingface_text_splitter import HuggingfaceTextSplitter
from app.application.processors.text_splitters.char_tiktoken_text_splitter import CharTiktokenTextSplitter
from app.application.processors.text_splitters.char_text_splitter import CharTextSplitter


class TextSplitterFactory:
    def __init__(self):
        self._splitters: Dict[str, TextSplitterInterface] = {
            "token": TokenTextSplitter(),
            "spacy": SpacyTextSplitter(),
            "sentence_transformer": SentenceTransformerTextSplitter(),
            "semantic": SemanticTextSplitter(),
            "recursive": RecursiveTextSplitter(),
            "huggingface": HuggingfaceTextSplitter(),
            "char_tiktoken": CharTiktokenTextSplitter(),
            "char": CharTextSplitter()
        }

    def get_text_splitter(self,
                     method: str) -> TextSplitterInterface:
        if method not in self._splitters:
            raise ValueError(f"Método de chunking no soportado: {method}")
        return self._splitters[method]
