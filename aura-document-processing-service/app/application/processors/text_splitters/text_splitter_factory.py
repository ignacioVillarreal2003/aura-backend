from typing import Dict, Type

from app.application.processors.text_splitters.adapters.recursive_text_splitter_adapter import (
    RecursiveTextSplitterAdapter
)
from app.application.processors.text_splitters.exceptions.text_splitter_exception import (
    UnsupportedTextSplitterMethodError
)
from app.application.processors.text_splitters.interfaces.text_splitter_adapter_interface import (
    TextSplitterAdapterInterface
)
from app.application.processors.text_splitters.constants.text_splitter_type import TextSplitterType


class TextSplitterFactory:
    def __init__(
            self
    ):
        self._splitters: Dict[TextSplitterType, Type[TextSplitterAdapterInterface]] = {
            TextSplitterType.recursive: RecursiveTextSplitterAdapter
        }
        self._instances: Dict[str, TextSplitterAdapterInterface] = {}

    def get_text_splitter(
            self,
            method: TextSplitterType
    ) -> TextSplitterAdapterInterface:
        if method not in self._splitters:
            raise UnsupportedTextSplitterMethodError(method)

        if method not in self._instances:
            self._instances[method] = self._splitters[method]()

        return self._instances[method]
