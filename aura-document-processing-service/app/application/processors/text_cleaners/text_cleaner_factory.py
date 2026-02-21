from typing import Dict, Type

from app.application.processors.text_cleaners.adapters.space_text_cleaner_adapter import SpaceTextCleanerAdapter
from app.application.processors.text_cleaners.exceptions.text_cleaner_exception import (
    UnsupportedTextCleanerTypeException
)
from app.application.processors.text_cleaners.interfaces.text_cleaner_adapter_interface import (
    TextCleanerAdapterInterface
)
from app.application.processors.text_cleaners.constants.text_cleaner_type import TextCleanerType


class TextCleanerFactory:
    def __init__(
            self
    ):
        self._cleaners: Dict[TextCleanerType, Type[TextCleanerAdapterInterface]] = {
            TextCleanerType.space: SpaceTextCleanerAdapter
        }
        self._instances: Dict[str, TextCleanerAdapterInterface] = {}

    def get_text_cleaner(
            self,
            type: TextCleanerType
    ) -> TextCleanerAdapterInterface:
        if type not in self._cleaners:
            raise UnsupportedTextCleanerTypeException(type)

        if type not in self._instances:
            self._instances[type] = self._cleaners[type]()

        return self._instances[type]
