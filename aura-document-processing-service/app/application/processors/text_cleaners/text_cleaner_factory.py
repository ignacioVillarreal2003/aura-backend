from typing import Dict, Type

from app.application.processors.text_cleaners.adapters.full_text_cleaner_adapter import FullTextCleanerAdapter
from app.application.processors.text_cleaners.adapters.no_line_breaks_text_cleaner_adapter import (
    NoLineBreaksTextCleanerAdapter
)
from app.application.processors.text_cleaners.adapters.space_text_cleaner_adapter import SpaceTextCleanerAdapter
from app.application.processors.text_cleaners.exceptions.text_cleaner_exception import UnsupportedTextCleanerMethodError
from app.application.processors.text_cleaners.interfaces.text_cleaner_adapter_interface import (
    TextCleanerAdapterInterface
)
from app.domain.constants.text_cleaner_type import TextCleanerType


class TextCleanerFactory:
    def __init__(
            self
    ):
        self._cleaners: Dict[TextCleanerType, Type[TextCleanerAdapterInterface]] = {
            TextCleanerType.FULL: FullTextCleanerAdapter,
            TextCleanerType.NO_LINE_BREAKS: NoLineBreaksTextCleanerAdapter,
            TextCleanerType.SPACE: SpaceTextCleanerAdapter
        }
        self._instances: Dict[str, TextCleanerAdapterInterface] = {}

    def get_text_cleaner(
            self,
            method: TextCleanerType
    ) -> TextCleanerAdapterInterface:
        if method not in self._cleaners:
            raise UnsupportedTextCleanerMethodError(method)

        if method not in self._instances:
            self._instances[method] = self._cleaners[method]()

        return self._instances[method]
