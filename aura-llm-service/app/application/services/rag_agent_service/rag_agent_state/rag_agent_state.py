import operator
from typing import Annotated, List, TypedDict

from langchain_core.messages import AnyMessage

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse


class RagAgentState(TypedDict):
    authenticated_user: AuthenticatedUser
    messages: Annotated[List[AnyMessage], operator.add]
    query: str
    keywords: List[str]
    retrieved_fragments: List[FragmentResponse]
    context: str
    context_sufficient: bool
    reasoning: str
    answer: str
    fallback_triggered: bool
