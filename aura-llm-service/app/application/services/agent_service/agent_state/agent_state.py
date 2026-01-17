import operator
from typing import Annotated, List, TypedDict
from langchain_core.messages import AnyMessage

from app.application.services.agent_service.constants.sentimient import Sentiment


class AgentState(TypedDict):
    messages: Annotated[List[AnyMessage], operator.add]
    sentiment: Sentiment
