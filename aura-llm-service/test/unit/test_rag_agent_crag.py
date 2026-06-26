"""Tests for the Corrective-RAG additions to the RAG agent: the grader node
verdict + fail-open behaviour, the refiner's bounded-loop counter, the grader
routing, and an end-to-end workflow run that exercises the refine→re-retrieve
loop with fakes (no real LLM/HTTP)."""
import types

from app.application.services.user_interactions.rag_agent_service.constants.rag_node_name import RagNodeName
from app.application.services.user_interactions.rag_agent_service.nodes.context_grader_node.context_grader_node import (
    ContextGraderNode,
)
from app.application.services.user_interactions.rag_agent_service.nodes.query_refiner_node.query_refiner_node import (
    QueryRefinerNode,
)
from app.application.services.user_interactions.rag_agent_service.rag_agent_settings import (
    ContextGraderSettings,
    QueryRefinerSettings,
    RagAgentServiceSettings,
)
from app.application.services.user_interactions.rag_agent_service.rag_agent_workflow import (
    RagAgentWorkflow,
    _route_after_grader,
)


class _FakeFacade:
    async def get_llm_base(self):
        return "llm"

    async def get_llm_json(self):
        return "llm-json"


class _ScriptedInvoker:
    """Returns queued responses in order; repeats the last once exhausted."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    async def call_llm_content(self, llm, llm_input):
        self.calls += 1
        return self._responses[min(self.calls - 1, len(self._responses) - 1)]


# --------------------------- grader routing ---------------------------

class TestGraderRouting:
    def test_sufficient_goes_to_synthesizer(self):
        state = {"context_sufficient": True}
        assert _route_after_grader(state) == RagNodeName.answer_synthesizer.value

    def test_insufficient_with_retry_goes_to_refiner(self):
        state = {"context_sufficient": False, "can_retry": True}
        assert _route_after_grader(state) == RagNodeName.query_refiner.value

    def test_insufficient_no_retry_best_effort_synthesizes(self):
        state = {"context_sufficient": False, "can_retry": False, "graph_facts": "x"}
        assert _route_after_grader(state) == RagNodeName.answer_synthesizer.value

    def test_insufficient_no_retry_no_context_falls_back(self):
        state = {"context_sufficient": False, "can_retry": False, "retrieved_fragments": [], "graph_facts": ""}
        assert _route_after_grader(state) == RagNodeName.fallback.value


# --------------------------- grader node ---------------------------

class TestContextGraderNode:
    def _node(self, invoker, max_attempts=1):
        return ContextGraderNode(_FakeFacade(), invoker, ContextGraderSettings(), max_attempts)

    async def test_sufficient_verdict(self):
        node = self._node(_ScriptedInvoker(['{"sufficient": true, "reason": "ok"}']))
        out = await node.process({"query": "q", "context": "ctx", "retrieval_attempts": 0})
        assert out["context_sufficient"] is True
        assert out["can_retry"] is False

    async def test_insufficient_sets_can_retry_within_budget(self):
        node = self._node(_ScriptedInvoker(['{"sufficient": false, "reason": "no"}']), max_attempts=1)
        out = await node.process({"query": "q", "context": "ctx", "retrieval_attempts": 0})
        assert out["context_sufficient"] is False
        assert out["can_retry"] is True

    async def test_insufficient_no_retry_when_budget_exhausted(self):
        node = self._node(_ScriptedInvoker(['{"sufficient": false, "reason": "no"}']), max_attempts=1)
        out = await node.process({"query": "q", "context": "ctx", "retrieval_attempts": 1})
        assert out["can_retry"] is False

    async def test_empty_context_is_insufficient(self):
        node = self._node(_ScriptedInvoker(["unused"]))
        out = await node.process({"query": "q", "context": "", "graph_facts": "", "retrieval_attempts": 0})
        assert out["context_sufficient"] is False

    async def test_llm_error_fails_open(self):
        class _Boom:
            async def call_llm_content(self, llm, llm_input):
                raise RuntimeError("down")

        node = self._node(_Boom())
        out = await node.process({"query": "q", "context": "ctx", "retrieval_attempts": 0})
        assert out["context_sufficient"] is True
        assert out["can_retry"] is False


# --------------------------- refiner node ---------------------------

class TestQueryRefinerNode:
    def _node(self, invoker):
        return QueryRefinerNode(_FakeFacade(), invoker, QueryRefinerSettings())

    async def test_increments_attempts_and_rewrites(self):
        node = self._node(_ScriptedInvoker(["consulta reformulada"]))
        out = await node.process({"query": "original", "retrieval_attempts": 0})
        assert out["retrieval_attempts"] == 1
        assert out["query"] == "consulta reformulada"

    async def test_failure_keeps_original_but_still_counts(self):
        class _Boom:
            async def call_llm_content(self, llm, llm_input):
                raise RuntimeError("down")

        node = self._node(_Boom())
        out = await node.process({"query": "original", "retrieval_attempts": 0})
        assert out["query"] == "original"
        assert out["retrieval_attempts"] == 1


# --------------------------- end-to-end loop ---------------------------

class _FakeDocsProvider:
    """First retrieval returns nothing relevant; after one refinement it returns
    a fragment. Lets us prove the corrective loop actually re-retrieves."""

    def __init__(self, make_fragment):
        self._make_fragment = make_fragment
        self.retrieve_calls = 0

    async def retrieve_context_fragments_by_question_request(self, *, authenticated_user, request):
        self.retrieve_calls += 1
        # Pass 1: an irrelevant fragment (graded insufficient). Pass 2: the answer.
        if self.retrieve_calls == 1:
            return types.SimpleNamespace(fragments=[self._make_fragment(content="texto irrelevante")])
        return types.SimpleNamespace(fragments=[self._make_fragment(content="respuesta encontrada")])

    async def retrieve_context_fragments_by_document(self, *, authenticated_user, document_ids):
        return types.SimpleNamespace(fragments=[])


async def test_corrective_loop_reretrieves_then_answers(make_fragment):
    from app.application.services.user_interactions.rag_agent_service.rag_agent_state.rag_agent_state_builder import (
        RagAgentStateBuilder,
    )
    from app.domain.authentication.authenticated_user import AuthenticatedUser
    from app.domain.constants.message_role import MessageRole
    from app.domain.dtos.message import Message
    from app.domain.dtos.user_interactions.agent.agent_request import AgentRequest

    docs = _FakeDocsProvider(make_fragment)

    # query_analyzer (1), grader pass1 -> insufficient (1), refiner (1),
    # grader pass2 -> sufficient (1), answer_synthesizer (1).
    invoker = _ScriptedInvoker([
        '{"query": "consulta", "keywords": ["a"], "intent": "question"}',  # analyzer
        '{"sufficient": false, "reason": "vacío"}',                          # grade pass 1
        "consulta mejor",                                                    # refiner
        '{"sufficient": true, "reason": "ok"}',                              # grade pass 2
        "Respuesta final basada en el contexto.",                           # synthesizer
    ])

    settings = RagAgentServiceSettings(
        use_context_grader=True,
        max_retrieval_attempts=1,
        use_guardrails=False,
        use_graph_context=False,
        use_graph_structured_query=False,
    )
    workflow = RagAgentWorkflow(
        ollama_llm_facade=_FakeFacade(),
        ollama_llm_invoker=invoker,
        document_context_provider=docs,
        settings=settings,
        graph_context_provider=None,
    )
    await workflow.build()

    request = AgentRequest(
        messages=[Message(role=MessageRole.human, content="¿pregunta?")],
        chat_id=1,
    )
    state = RagAgentStateBuilder().build(
        agent_request=request,
        authenticated_user=AuthenticatedUser(id=1, email="u@test.com"),
    )
    final = await workflow.invoke(state)

    assert docs.retrieve_calls == 2  # initial + one corrective retry
    assert final["answer"] == "Respuesta final basada en el contexto."
    assert len(final["retrieved_fragments"]) == 1


async def test_stream_emits_initial_and_per_node_spanish_progress(make_fragment):
    from app.application.services.user_interactions.rag_agent_service.rag_agent_service import RagAgentService
    from app.domain.authentication.authenticated_user import AuthenticatedUser
    from app.domain.constants.message_role import MessageRole
    from app.domain.dtos.message import Message
    from app.domain.dtos.user_interactions.agent.agent_request import AgentRequest
    from app.domain.dtos.user_interactions.agent.agent_stream_events import (
        AgentStreamComplete,
        AgentStreamProgress,
    )

    class _Docs:
        async def retrieve_context_fragments_by_question_request(self, *, authenticated_user, request):
            return types.SimpleNamespace(fragments=[make_fragment(content="ctx")])

        async def retrieve_context_fragments_by_document(self, *, authenticated_user, document_ids):
            return types.SimpleNamespace(fragments=[make_fragment(content="ctx")])

    invoker = _ScriptedInvoker([
        '{"query": "q", "keywords": ["a"], "intent": "question"}',  # analyzer
        '{"sufficient": true, "reason": "ok"}',                      # grader
        "Respuesta final.",                                         # synthesizer
    ])
    settings = RagAgentServiceSettings(
        use_guardrails=False, use_graph_context=False, use_graph_structured_query=False
    )
    svc = RagAgentService(_FakeFacade(), invoker, _Docs(), settings, graph_context_provider=None)
    request = AgentRequest(
        messages=[Message(role=MessageRole.human, content="hola")], chat_id=1
    )
    user = AuthenticatedUser(id=1, email="u@test.com")

    events = [e async for e in svc.execute_stream(request, user)]
    progress = [e for e in events if isinstance(e, AgentStreamProgress)]

    # The first event is always the initial "processing" status (Spanish, eager).
    assert progress[0].step == "processing"
    assert progress[0].message == "Procesando tu consulta..."
    # Node progress is emitted before each node runs, in pipeline order.
    steps = [p.step for p in progress]
    assert steps[:4] == [
        "processing",
        RagNodeName.query_analyzer.value,
        RagNodeName.graph_context_retriever.value,
        RagNodeName.context_retriever.value,
    ]
    # Every progress event carries a non-empty Spanish message for the frontend.
    assert all(p.message and p.message.strip() for p in progress)
    assert any(isinstance(e, AgentStreamComplete) for e in events)


async def test_execute_records_outcome_metric(make_fragment):
    from app.application.services.generation_shared.generation_observability import generation_total
    from app.application.services.user_interactions.rag_agent_service.rag_agent_service import RagAgentService
    from app.domain.authentication.authenticated_user import AuthenticatedUser
    from app.domain.constants.message_role import MessageRole
    from app.domain.dtos.message import Message
    from app.domain.dtos.user_interactions.agent.agent_request import AgentRequest

    class _Docs:
        async def retrieve_context_fragments_by_question_request(self, *, authenticated_user, request):
            return types.SimpleNamespace(fragments=[make_fragment(content="ctx")])

        async def retrieve_context_fragments_by_document(self, *, authenticated_user, document_ids):
            return types.SimpleNamespace(fragments=[make_fragment(content="ctx")])

    invoker = _ScriptedInvoker([
        '{"query": "q", "keywords": [], "intent": "question"}',
        '{"sufficient": true, "reason": "ok"}',
        "Respuesta.",
    ])
    settings = RagAgentServiceSettings(
        use_guardrails=False, use_graph_context=False, use_graph_structured_query=False
    )
    svc = RagAgentService(_FakeFacade(), invoker, _Docs(), settings, graph_context_provider=None)
    request = AgentRequest(messages=[Message(role=MessageRole.human, content="hola")], chat_id=1)
    user = AuthenticatedUser(id=1, email="u@test.com")

    counter = generation_total.labels(label="rag-agent", call_mode="sync", outcome="success")
    before = counter._value.get()
    await svc.execute(request, user)
    assert counter._value.get() == before + 1
