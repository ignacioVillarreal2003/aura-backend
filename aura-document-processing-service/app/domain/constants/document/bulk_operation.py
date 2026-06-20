from enum import Enum


class BulkOperation(str, Enum):
    reembed = "reembed"
    reprocess = "reprocess"
    enrich = "enrich"
    graph_extract = "graph_extract"
