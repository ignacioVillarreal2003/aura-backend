from typing import Protocol


class DocumentListenerInterface(Protocol):
    def start_consuming(self) -> None:
        ...

    def close(self) -> None:
        ...