"""
Define la interfaz base para todos los divisores de texto. 
Obliga a implementar el método split_text en las clases derivadas, 
garantizando una API consistente para todos los splitters.

Uso principal:
    - Servir como contrato para la implementación de nuevos divisores de texto.
    - Facilitar la integración y el intercambio de estrategias de segmentación.
"""

from abc import ABC, abstractmethod
from typing import List

class TextSplitterInterface(ABC):
    """
    Interfaz abstracta para divisores de texto.

    Métodos abstractos:
        split_text(text: str, size: int, overlap: int) -> List[str]:
            Divide el texto en fragmentos según los parámetros especificados.

    Args:
        text (str): Texto a dividir.
        size (int): Tamaño máximo de cada fragmento.
        overlap (int): Número de elementos que se solapan entre fragmentos.

    Returns:
        List[str]: Lista de fragmentos de texto.
    """
    @abstractmethod
    def split_text(self, text: str, size: int, overlap: int) -> List[str]:
        pass