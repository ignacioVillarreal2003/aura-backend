from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationSettings:
    history_messages_window: int = 4

    use_keywords: bool = True
    semantic_fragments_per_lane: int = 2
    bm25_fragments_per_lane: int = 3
    use_rerank: bool = True
    max_rag_fragments: int = 12
    adjacent_chunks: int = 1

    max_attached_fragments: int = 40
    attached_reserve_ratio: float = 0.6

    enable_context_reduction: bool = True
    reduction_batch_chars: int = 8_000
    max_reduction_passes: int = 3

    max_context_chars: int = 10_000
