from typing import Dict
from .interfaces.text_cleaner_interface import TextCleanerInterface
from .basic_text_cleaner import BasicTextCleaner

class TextCleanerFactory:
    def __init__(self):
        self._cleaners: Dict[str, TextCleanerInterface] = {
            "basic": BasicTextCleaner()
        }

    def get_cleaner(self, method: str) -> TextCleanerInterface:
        if method not in self._cleaners:
            raise ValueError(f"Método de limpieza no soportado: {method}")
        return self._cleaners[method]
