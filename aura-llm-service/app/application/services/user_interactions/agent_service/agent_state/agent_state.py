import operator
from typing import Annotated, List, Optional, TypedDict
from langchain_core.messages import AnyMessage

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse


class AgentState(TypedDict):
    authenticated_user: AuthenticatedUser
    messages: Annotated[List[AnyMessage], operator.add]
    chat_id: int
    operator_system_prompt: Optional[str]
    response_style: Optional[str]
    normalized_query: str
    resolved_query: str
    intent: str
    keywords: List[str]
    retrieved_fragments: List[FragmentResponse]
    context: str
    answer: str
    guardrail_passed: bool
    fallback_triggered: bool
