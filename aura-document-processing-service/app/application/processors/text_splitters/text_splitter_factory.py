from typing import Dict, Type

from app.application.processors.text_splitters.adapters.char_text_splitter_adapter import CharTextSplitterAdapter
from app.application.processors.text_splitters.adapters.char_tiktoken_text_splitter_adapter import (
    CharTiktokenTextSplitterAdapter
)
from app.application.processors.text_splitters.adapters.huggingface_text_splitter_adapter import (
    HuggingfaceTextSplitterAdapter
)
from app.application.processors.text_splitters.adapters.recursive_text_splitter_adapter import (
    RecursiveTextSplitterAdapter
)
from app.application.processors.text_splitters.adapters.semantic_text_splitter_adapter import (
    SemanticTextSplitterAdapter
)
from app.application.processors.text_splitters.adapters.sentence_transformer_text_splitter_adapter import (
    SentenceTransformerTextSplitterAdapter
)
from app.application.processors.text_splitters.adapters.spacy_text_splitter_adapter import SpacyTextSplitterAdapter
from app.application.processors.text_splitters.adapters.token_text_splitter_adapter import TokenTextSplitterAdapter
from app.application.processors.text_splitters.exceptions.text_splitter_exception import (
    UnsupportedTextSplitterMethodError
)
from app.application.processors.text_splitters.interfaces.text_splitter_adapter_interface import (
    TextSplitterAdapterInterface
)
from app.domain.constants.text_splitter_type import TextSpliterType


class TextSplitterFactory:
    def __init__(
            self
    ):
        self._splitters: Dict[TextSpliterType, Type[TextSplitterAdapterInterface]] = {
            TextSpliterType.TOKEN: TokenTextSplitterAdapter,
            TextSpliterType.SPACY: SpacyTextSplitterAdapter,
            TextSpliterType.SENTENCE_TRANSFORMER: SentenceTransformerTextSplitterAdapter,
            TextSpliterType.SEMANTIC: SemanticTextSplitterAdapter,
            TextSpliterType.RECURSIVE: RecursiveTextSplitterAdapter,
            TextSpliterType.HUGGINGFACE: HuggingfaceTextSplitterAdapter,
            TextSpliterType.CHAR_TIKTOKEN: CharTiktokenTextSplitterAdapter,
            TextSpliterType.CHAR: CharTextSplitterAdapter
        }
        self._instances: Dict[str, TextSplitterAdapterInterface] = {}

    def get_text_splitter(
            self,
            method: TextSpliterType
    ) -> TextSplitterAdapterInterface:
        if method not in self._splitters:
            raise UnsupportedTextSplitterMethodError(method)

        if method not in self._instances:
            self._instances[method] = self._splitters[method]()

        return self._instances[method]
