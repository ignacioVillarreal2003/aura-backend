import operator
from typing import Annotated, List, TypedDict
from langchain_core.messages import AnyMessage

from app.domain.constants.sentimient import Sentiment


class AgentState(TypedDict):
    messages: Annotated[List[AnyMessage], operator.add]
    sentiment: Sentiment
