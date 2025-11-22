from typing import Dict, Type

from app.application.exceptions.api_exceptions import UnsupportedTextSplitterMethodError
from app.application.processors.text_splitters.adapters.char_text_splitter_adapter import CharTextSplitterAdapter
from app.application.processors.text_splitters.adapters.char_tiktoken_text_splitter_adapter import \
    CharTiktokenTextSplitterAdapter
from app.application.processors.text_splitters.adapters.huggingface_text_splitter_adapter import \
    HuggingfaceTextSplitterAdapter
from app.application.processors.text_splitters.interfaces.text_splitter_interface import TextSplitterInterface
from app.application.processors.text_splitters.adapters.recursive_text_splitter_adapter import \
    RecursiveTextSplitterAdapter
from app.application.processors.text_splitters.adapters.semantic_text_splitter_adapter import \
    SemanticTextSplitterAdapter
from app.application.processors.text_splitters.adapters.sentence_transformer_text_splitter_adapter import \
    SentenceTransformerTextSplitterAdapter
from app.application.processors.text_splitters.adapters.spacy_text_splitter_adapter import SpacyTextSplitterAdapter
from app.application.processors.text_splitters.adapters.token_text_splitter_adapter import TokenTextSplitterAdapter


class TextSplitterFactory:
    def __init__(self):
        self._splitters: Dict[str, Type[TextSplitterInterface]] = {
            "token": TokenTextSplitterAdapter,
            "spacy": SpacyTextSplitterAdapter,
            "sentence_transformer": SentenceTransformerTextSplitterAdapter,
            "semantic": SemanticTextSplitterAdapter,
            "recursive": RecursiveTextSplitterAdapter,
            "huggingface": HuggingfaceTextSplitterAdapter,
            "char_tiktoken": CharTiktokenTextSplitterAdapter,
            "char": CharTextSplitterAdapter
        }
        self._instances: Dict[str, TextSplitterInterface] = {}

    def get_text_splitter(self,
                          method: str) -> TextSplitterInterface:
        if method not in self._splitters:
            raise UnsupportedTextSplitterMethodError(method)

        if method not in self._instances:
            self._instances[method] = self._splitters[method]()

        return self._instances[method]
