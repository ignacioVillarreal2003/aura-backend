import operator
from typing import Annotated, List, Optional, TypedDict

from langchain_core.messages import AnyMessage

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse


class RagAgentState(TypedDict):
    authenticated_user: AuthenticatedUser
    messages: Annotated[List[AnyMessage], operator.add]
    chat_id: int
    operator_system_prompt: Optional[str]
    response_style: Optional[str]
    query: str
    keywords: List[str]
    retrieved_fragments: List[FragmentResponse]
    context: str
    answer: str
    fallback_triggered: bool
