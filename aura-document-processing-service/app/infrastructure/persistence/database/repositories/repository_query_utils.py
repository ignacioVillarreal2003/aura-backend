from collections.abc import Iterator, Sequence

DEFAULT_IN_CLAUSE_CHUNK_SIZE = 500


def chunked_ids(document_ids: Sequence[int], chunk_size: int = DEFAULT_IN_CLAUSE_CHUNK_SIZE) -> Iterator[list[int]]:
    seen: set[int] = set()
    ordered_unique: list[int] = []
    for doc_id in document_ids:
        if doc_id in seen:
            continue
        seen.add(doc_id)
        ordered_unique.append(doc_id)
    for i in range(0, len(ordered_unique), chunk_size):
        yield ordered_unique[i: i + chunk_size]
