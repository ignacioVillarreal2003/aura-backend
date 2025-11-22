from typing import Protocol


class QuestionListenerInterface(Protocol):
    def start_consuming(self,
                        prefetch_count: int) -> None:
        ...

    def start_consuming_background(self, prefetch_count: int = 1) -> None:
        ...

    def stop_consuming(self) -> None:
        ...