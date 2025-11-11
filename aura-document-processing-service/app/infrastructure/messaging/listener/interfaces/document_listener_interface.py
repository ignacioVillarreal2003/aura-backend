from typing import Protocol, Callable, Optional


class DocumentListenerInterface(Protocol):
    def start_consuming(
        self,
        callback: Callable[[dict], None],
        prefetch_count: int = 1
    ) -> None:
        ...

    def start_consuming_background(
        self,
        callback: Callable[[dict], None],
        prefetch_count: int = 1
    ) -> None:
        ...

    def stop_consuming(self) -> None:
        ...

    def is_consuming(self) -> bool:
        ...
