from typing import Dict

from app.application.processors.text_cleaners.basic_text_cleaner import BasicTextCleaner
from app.application.processors.text_cleaners.interfaces.text_cleaner_interface import TextCleanerInterface


class TextCleanerFactory:
    def __init__(self):
        self._cleaners: Dict[str, TextCleanerInterface] = {
            "basic": BasicTextCleaner()
        }

    def get_text_cleaner(self,
                    method: str) -> TextCleanerInterface:
        if method not in self._cleaners:
            raise ValueError(f"Método de limpieza no soportado: {method}")
        return self._cleaners[method]
