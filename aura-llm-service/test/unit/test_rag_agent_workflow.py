from app.application.services.user_interactions.rag_agent_service.constants.rag_node_name import RagNodeName
from app.application.services.user_interactions.rag_agent_service.context_formatting import build_document_context
from app.application.services.user_interactions.rag_agent_service.nodes.query_analyzer_node.query_analyzer_node import (
    QueryAnalyzerNode,
)
from app.application.services.user_interactions.rag_agent_service.rag_agent_settings import QueryAnalyzerSettings
from app.application.services.user_interactions.rag_agent_service.rag_agent_workflow import (
    _route_after_graph_retriever,
    _route_after_guardrails,
    _route_after_retrieval,
)


class TestRouting:
    def test_question_intent_goes_to_context_retriever(self):
        assert _route_after_graph_retriever({"intent": "question"}) == RagNodeName.context_retriever.value

    def test_document_lookup_intent_goes_to_document_fetcher(self):
        assert (
            _route_after_graph_retriever({"intent": "document_lookup"})
            == RagNodeName.document_fetcher.value
        )

    def test_relational_intent_goes_to_context_retriever(self):
        assert (
            _route_after_graph_retriever({"intent": "relational"})
            == RagNodeName.context_retriever.value
        )

    def test_no_context_routes_to_fallback(self):
        state = {"retrieved_fragments": [], "graph_facts": ""}
        assert _route_after_retrieval(state) == RagNodeName.fallback.value

    def test_graph_facts_alone_allow_synthesis(self):
        state = {"retrieved_fragments": [], "graph_facts": "hecho"}
        assert _route_after_retrieval(state) == RagNodeName.answer_synthesizer.value

    def test_guardrail_rejection_routes_to_fallback(self):
        assert _route_after_guardrails({"guardrail_passed": False}) == RagNodeName.fallback.value


class TestQueryAnalyzerParsing:
    def _parse(self, raw):
        node = QueryAnalyzerNode(
            ollama_llm_facade=None, ollama_llm_invoker=None, settings=QueryAnalyzerSettings()
        )
        return node._parse_response(raw, fallback_query="fallback")

    def test_valid_json_with_intent(self):
        result = self._parse(
            '{"query": "q", "keywords": ["a", "b"], "intent": "document_lookup"}'
        )
        assert result == {"query": "q", "keywords": ["a", "b"], "intent": "document_lookup"}

    def test_missing_intent_defaults_to_question(self):
        assert self._parse('{"query": "q", "keywords": []}')["intent"] == "question"

    def test_unknown_intent_defaults_to_question(self):
        raw = '{"query": "q", "keywords": [], "intent": "inventado"}'
        assert self._parse(raw)["intent"] == "question"

    def test_relational_intent_is_preserved(self):
        raw = '{"query": "q", "keywords": [], "intent": "relational"}'
        assert self._parse(raw)["intent"] == "relational"

    def test_garbage_falls_back_to_original_query(self):
        result = self._parse("sin json")
        assert result == {"query": "fallback", "keywords": [], "intent": "question"}

    def test_keywords_capped_to_settings_max(self):
        keywords = [f"k{i}" for i in range(40)]
        raw = f'{{"query": "q", "keywords": {keywords}, "intent": "question"}}'.replace("'", '"')
        assert len(self._parse(raw)["keywords"]) == QueryAnalyzerSettings().max_keywords


class TestBuildDocumentContext:
    def test_groups_by_document_and_sorts_fragments(self, make_fragment):
        fragments = [
            make_fragment(fragment_id=1, document_id=7, document_name="Doc A", fragment_index=1, content="segundo"),
            make_fragment(fragment_id=2, document_id=7, document_name="Doc A", fragment_index=0, content="primero"),
        ]
        context = build_document_context(fragments, max_context_chars=1000)
        assert "Documento #7 — Doc A" in context
        assert context.index("primero") < context.index("segundo")

    def test_empty_returns_empty_string(self):
        assert build_document_context([], max_context_chars=100) == ""

    def test_respects_char_budget(self, make_fragment):
        fragments = [
            make_fragment(fragment_id=1, document_id=1, content="a" * 300),
            make_fragment(fragment_id=2, document_id=2, content="b" * 300),
        ]
        context = build_document_context(fragments, max_context_chars=350)
        assert "a" * 200 in context
        assert "b" * 300 not in context

    def test_fragment_header_includes_page_and_heading(self, make_fragment):
        fragments = [
            make_fragment(content="texto", page_number=3, heading="Introducción"),
        ]
        context = build_document_context(fragments, max_context_chars=1000)
        assert "[Fragmento 1 · pág. 3 · Introducción]" in context

    def test_fragment_header_falls_back_to_section_path(self, make_fragment):
        fragments = [
            make_fragment(content="texto", section_path="Capítulo 1 > Sección 2"),
        ]
        context = build_document_context(fragments, max_context_chars=1000)
        assert "[Fragmento 1 · Capítulo 1 > Sección 2]" in context

    def test_fragment_header_without_metadata_stays_plain(self, make_fragment):
        fragments = [make_fragment(content="texto")]
        context = build_document_context(fragments, max_context_chars=1000)
        assert "[Fragmento 1]" in context
