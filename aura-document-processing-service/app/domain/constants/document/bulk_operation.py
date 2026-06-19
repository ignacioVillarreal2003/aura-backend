from enum import Enum


class BulkOperation(str, Enum):
    """A maintenance operation that can be fanned out over 1, several or all documents.

    The value doubles as the per-operation key segment for the bulk job progress
    store, so a single migration of each kind runs at a time.
    """
    reembed = "reembed"
    reprocess = "reprocess"
    enrich = "enrich"
    graph_extract = "graph_extract"
