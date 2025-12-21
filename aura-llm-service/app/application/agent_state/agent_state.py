import operator
from typing import Annotated, List, TypedDict, Optional
from langchain_core.messages import AnyMessage


class AgentState(TypedDict):
    messages: Annotated[List[AnyMessage], operator.add]
    sentiment: str
    summary: Optional[str]
