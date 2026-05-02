from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

from app.domain.dtos.fragment.fragment_query.fragment_list_response import FragmentListResponse
from app.domain.dtos.graph.graph_query.graph_query_response import GraphQueryResponse


class HybridRetrievalSource(str, Enum):
    KNOWLEDGE_GRAPH = "kg"
    VECTOR_SEARCH = "rag"
    NONE = "none"


class GraphHybridQueryResponse(BaseModel):
    """Response of the hybrid orchestrator endpoint.

    The orchestrator never mixes results from the KG and RAG paths into a
    single ranked list (that is intentionally out of scope to keep the
    layers decoupled). It picks ONE primary source and exposes it via
    ``source``; the alternate field is left empty when not used.
    """

    source: HybridRetrievalSource = Field(...)
    confidence: float = Field(..., ge=0.0, le=1.0)
    fallback_used: bool = Field(...)
    kg_results: Optional[GraphQueryResponse] = Field(default=None)
    rag_results: Optional[FragmentListResponse] = Field(default=None)
