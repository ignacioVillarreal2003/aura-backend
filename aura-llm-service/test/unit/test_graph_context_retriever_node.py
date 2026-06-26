from app.application.services.user_interactions.rag_agent_service.nodes.graph_context_retriever_node.graph_context_retriever_node import (
    GraphContextRetrieverNode,
)
from app.application.services.user_interactions.rag_agent_service.rag_agent_settings import RagAgentServiceSettings
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.graph_context_provider.dtos.graph_context_dtos import (
    GraphContextResult,
    GraphQueryResult,
)


class FakeGraphContextProvider:
    def __init__(
            self,
            *,
            context_text: str = "",
            query_text: str = "",
            is_active: bool = True,
    ) -> None:
        self._context_text = context_text
        self._query_text = query_text
        self._is_active = is_active
        self.retrieve_calls: list[dict] = []
        self.query_calls: list[dict] = []

    @property
    def is_active(self) -> bool:
        return self._is_active

    async def retrieve_graph_context(self, **kwargs) -> GraphContextResult:
        self.retrieve_calls.append(kwargs)
        return GraphContextResult(context_text=self._context_text)

    async def execute_graph_query(self, **kwargs) -> GraphQueryResult:
        self.query_calls.append(kwargs)
        return GraphQueryResult(
            context_text=self._query_text,
            entities_count=1,
            relations_count=2,
        )


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(id=1, email="u@example.com")


def _state(intent: str) -> dict:
    return {
        "query": "¿cómo se conecta A con B?",
        "keywords": ["A", "B"],
        "intent": intent,
        "authenticated_user": _user(),
        "chat_id": 7,
    }


async def test_structured_query_skipped_when_flag_off():
    provider = FakeGraphContextProvider(context_text="kw", query_text="structured")
    settings = RagAgentServiceSettings(
        use_graph_context=True, use_graph_structured_query=False
    )
    node = GraphContextRetrieverNode(provider, settings)

    result = await node.process(_state("relational"))

    assert provider.query_calls == []
    assert result["graph_facts"] == "kw"


async def test_structured_query_runs_for_relational_intent():
    provider = FakeGraphContextProvider(context_text="kw", query_text="structured")
    settings = RagAgentServiceSettings(
        use_graph_context=True, use_graph_structured_query=True
    )
    node = GraphContextRetrieverNode(provider, settings)

    result = await node.process(_state("relational"))

    assert len(provider.query_calls) == 1
    assert result["graph_facts"] == "kw\nstructured"


async def test_structured_query_skipped_for_non_relational_intent():
    provider = FakeGraphContextProvider(context_text="kw", query_text="structured")
    settings = RagAgentServiceSettings(
        use_graph_context=True, use_graph_structured_query=True
    )
    node = GraphContextRetrieverNode(provider, settings)

    result = await node.process(_state("question"))

    assert provider.query_calls == []
    assert result["graph_facts"] == "kw"


async def test_structured_query_only_when_context_disabled():
    provider = FakeGraphContextProvider(context_text="kw", query_text="structured")
    settings = RagAgentServiceSettings(
        use_graph_context=False, use_graph_structured_query=True
    )
    node = GraphContextRetrieverNode(provider, settings)

    result = await node.process(_state("relational"))

    assert provider.retrieve_calls == []
    assert len(provider.query_calls) == 1
    assert result["graph_facts"] == "structured"


async def test_inactive_provider_returns_empty():
    provider = FakeGraphContextProvider(is_active=False)
    settings = RagAgentServiceSettings(use_graph_structured_query=True)
    node = GraphContextRetrieverNode(provider, settings)

    result = await node.process(_state("relational"))

    assert result["graph_facts"] == ""
    assert provider.retrieve_calls == []
    assert provider.query_calls == []
