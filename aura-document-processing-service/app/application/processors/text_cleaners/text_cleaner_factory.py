from typing import Dict, Type

from app.application.exceptions.api_exceptions import UnsupportedTextCleanerMethodError
from app.application.processors.text_cleaners.adapters.full_text_cleaner_adapter import FullTextCleanerAdapter
from app.application.processors.text_cleaners.interfaces.text_cleaner_interface import TextCleanerInterface
from app.application.processors.text_cleaners.adapters.no_line_breaks_text_cleaner_adapter import \
    NoLineBreaksTextCleanerAdapter
from app.application.processors.text_cleaners.adapters.space_text_cleaner_adapter import SpaceTextCleanerAdapter


class TextCleanerFactory:
    def __init__(self):
        self._cleaners: Dict[str, Type[TextCleanerInterface]] = {
            "full": FullTextCleanerAdapter,
            "no_line_breaks": NoLineBreaksTextCleanerAdapter,
            "space": SpaceTextCleanerAdapter
        }
        self._instances: Dict[str, TextCleanerInterface] = {}

    def get_text_cleaner(self,
                         method: str) -> TextCleanerInterface:
        if method not in self._cleaners:
            raise UnsupportedTextCleanerMethodError(method)

        if method not in self._instances:
            self._instances[method] = self._cleaners[method]()

        return self._instances[method]
