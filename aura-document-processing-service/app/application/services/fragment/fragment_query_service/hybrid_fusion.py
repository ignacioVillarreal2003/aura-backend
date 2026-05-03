from typing import Protocol, TypeVar


class _HasId(Protocol):
    id: int


T = TypeVar("T", bound=_HasId)


def reciprocal_rank_fusion(
        *,
        ranked_lists: list[list[T]],
        k: int = 60,
) -> list[T]:
    if not ranked_lists:
        return []

    scores: dict[int, float] = {}
    by_id: dict[int, T] = {}

    for ranked in ranked_lists:
        for rank, item in enumerate(ranked, start=1):
            fid = int(item.id)
            scores[fid] = scores.get(fid, 0.0) + 1.0 / (float(k) + float(rank))
            by_id.setdefault(fid, item)

    return sorted(
        by_id.values(),
        key=lambda f: scores[int(f.id)],
        reverse=True,
    )
