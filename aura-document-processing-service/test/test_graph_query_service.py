from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.services.graph.graph_query_service.graph_query_service import (
    GraphQueryService,
    _GraphIntentParameterError,
)
from app.application.services.graph.knowledge_graph_settings import KnowledgeGraphSettings
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.graph.entity_type import EntityType
from app.domain.constants.graph.query_intent import QueryIntent
from app.domain.dtos.graph.graph_entity.graph_entity_response import GraphEntityResponse
from app.domain.dtos.graph.graph_entity.graph_relation_response import (
    GraphRelationEndpoint,
    GraphRelationResponse,
)
from app.domain.dtos.graph.graph_query.graph_query_request import GraphQueryRequest



def _user(user_id: int = 1) -> AuthenticatedUser:
    return AuthenticatedUser(id=user_id, email="u@test.com", roles=[], permissions=[])


def _entity(name: str, etype: EntityType = EntityType.PERSON) -> GraphEntityResponse:
    return GraphEntityResponse(canonical_name=name, display_name=name.title(), type=etype)


def _endpoint(name: str, etype: EntityType = EntityType.PERSON) -> GraphRelationEndpoint:
    return GraphRelationEndpoint(canonical_name=name, display_name=name.title(), type=etype)


def _relation(source: str, target: str, rel_type: str = "works_for") -> GraphRelationResponse:
    return GraphRelationResponse(
        type=rel_type,
        source=_endpoint(source),
        target=_endpoint(target, EntityType.ORGANIZATION),
        confidence=0.9,
    )


def _translation(intent, *, parameters=None, confidence=0.5, reasoning="because"):
    return SimpleNamespace(
        intent=intent,
        parameters=parameters or {},
        confidence=confidence,
        reasoning=reasoning,
    )


def _make_service(
    *,
    llm=None,
    entity_repo=None,
    relation_repo=None,
    path_repo=None,
    catalog=None,
    settings=None,
):
    return GraphQueryService(
        llm_provider=llm or AsyncMock(),
        entity_repository=entity_repo or AsyncMock(),
        relation_repository=relation_repo or AsyncMock(),
        path_repository=path_repo,
        document_collection_catalog_client=catalog or AsyncMock(),
        knowledge_graph_settings=settings or KnowledgeGraphSettings(),
    )


def _catalog(ids):
    catalog = AsyncMock()
    catalog.fetch_all_accessible_document_ids = AsyncMock(return_value=ids)
    return catalog



class TestExecuteAccessControl:
    async def test_no_accessible_documents_returns_empty_unknown_without_calling_llm(self):
        llm = AsyncMock()
        service = _make_service(llm=llm, catalog=_catalog([]))

        response = await service.execute(
            request=GraphQueryRequest(question="who is bob?"),
            authenticated_user=_user(),
            database_session=MagicMock(),
            authorization_header="Bearer t",
        )

        assert response.intent == QueryIntent.UNKNOWN
        assert response.confidence == 0.0
        assert response.entities == []
        assert response.relations == []
        llm.translate_graph_query.assert_not_called()



class TestExecuteDispatch:
    async def test_find_entity_returns_prefix_results(self):
        entity_repo = AsyncMock()
        entity_repo.search_by_name_prefix = AsyncMock(return_value=[_entity("bob smith")])
        entity_repo.fulltext_search = AsyncMock(return_value=[])
        llm = AsyncMock()
        llm.translate_graph_query = AsyncMock(
            return_value=_translation(
                QueryIntent.FIND_ENTITY, parameters={"entity_name": "Bob Smith"}
            )
        )
        service = _make_service(llm=llm, entity_repo=entity_repo, catalog=_catalog([1, 2]))

        response = await service.execute(
            request=GraphQueryRequest(question="who is bob smith?"),
            authenticated_user=_user(),
            database_session=MagicMock(),
            authorization_header="Bearer t",
        )

        assert response.intent == QueryIntent.FIND_ENTITY
        assert [e.canonical_name for e in response.entities] == ["bob smith"]
        entity_repo.search_by_name_prefix.assert_awaited_once()
        assert entity_repo.search_by_name_prefix.await_args.kwargs["canonical_prefix"] == "bob smith"
        entity_repo.fulltext_search.assert_not_called()

    async def test_find_entity_falls_back_to_fulltext_when_prefix_empty(self):
        entity_repo = AsyncMock()
        entity_repo.search_by_name_prefix = AsyncMock(return_value=[])
        entity_repo.fulltext_search = AsyncMock(return_value=[_entity("bob")])
        llm = AsyncMock()
        llm.translate_graph_query = AsyncMock(
            return_value=_translation(
                QueryIntent.FIND_ENTITY, parameters={"entity_name": "bob"}
            )
        )
        service = _make_service(llm=llm, entity_repo=entity_repo, catalog=_catalog([1]))

        response = await service.execute(
            request=GraphQueryRequest(question="bob?"),
            authenticated_user=_user(),
            database_session=MagicMock(),
            authorization_header="Bearer t",
        )

        entity_repo.fulltext_search.assert_awaited_once()
        assert [e.canonical_name for e in response.entities] == ["bob"]

    async def test_empty_dispatch_triggers_question_level_fulltext_fallback(self):
        entity_repo = AsyncMock()
        entity_repo.list_by_type = AsyncMock(return_value=[])
        entity_repo.fulltext_search = AsyncMock(return_value=[_entity("acme")])
        llm = AsyncMock()
        llm.translate_graph_query = AsyncMock(
            return_value=_translation(
                QueryIntent.FILTER_BY_TYPE, parameters={"entity_type": "organization"}
            )
        )
        service = _make_service(llm=llm, entity_repo=entity_repo, catalog=_catalog([1]))

        response = await service.execute(
            request=GraphQueryRequest(question="list orgs"),
            authenticated_user=_user(),
            database_session=MagicMock(),
            authorization_header="Bearer t",
        )

        assert [e.canonical_name for e in response.entities] == ["acme"]
        entity_repo.fulltext_search.assert_awaited_once()

    async def test_invalid_intent_params_fall_back_to_fulltext_and_unknown_intent(self):
        entity_repo = AsyncMock()
        entity_repo.fulltext_search = AsyncMock(return_value=[_entity("topic")])
        llm = AsyncMock()
        llm.translate_graph_query = AsyncMock(
            return_value=_translation(
                QueryIntent.LIST_BY_DOCUMENT, parameters={"document_id": "not-a-number"}
            )
        )
        service = _make_service(llm=llm, entity_repo=entity_repo, catalog=_catalog([1]))

        response = await service.execute(
            request=GraphQueryRequest(question="what is in the doc?"),
            authenticated_user=_user(),
            database_session=MagicMock(),
            authorization_header="Bearer t",
        )

        assert response.intent == QueryIntent.UNKNOWN
        assert [e.canonical_name for e in response.entities] == ["topic"]



class TestDispatchHelpers:
    async def test_filter_by_type_requires_entity_type(self):
        service = _make_service()
        with pytest.raises(_GraphIntentParameterError):
            await service._handle_filter_by_type({}, [1], 10)

    async def test_list_by_document_rejects_non_positive_id(self):
        service = _make_service()
        with pytest.raises(_GraphIntentParameterError):
            await service._handle_list_by_document({"document_id": 0}, [1], 10)

    async def test_find_neighbors_returns_relations_only(self):
        relation_repo = AsyncMock()
        relation_repo.list_neighbors_of = AsyncMock(return_value=[_relation("bob", "acme")])
        service = _make_service(relation_repo=relation_repo)

        entities, relations = await service._handle_find_neighbors(
            {"entity_name": "Bob", "depth": 2}, [1], 10
        )

        assert entities == []
        assert len(relations) == 1
        assert relation_repo.list_neighbors_of.await_args.kwargs["canonical_name"] == "bob"

    async def test_find_path_without_target_uses_source_neighbors(self):
        relation_repo = AsyncMock()
        relation_repo.list_neighbors_of = AsyncMock(return_value=[_relation("bob", "acme")])
        service = _make_service(relation_repo=relation_repo)

        entities, relations = await service._handle_find_path(
            {"source_name": "Bob"}, [1], 10
        )

        assert entities == []
        assert len(relations) == 1
        relation_repo.list_neighbors_of.assert_awaited_once()

    async def test_dispatch_unknown_intent_returns_empty(self):
        service = _make_service()
        entities, relations = await service._dispatch_intent(
            intent=QueryIntent.UNKNOWN, params={}, accessible_ids=[1], max_results=10
        )
        assert entities == []
        assert relations == []



class TestFulltextFallback:
    async def test_repository_error_is_swallowed_and_returns_empty(self):
        entity_repo = AsyncMock()
        entity_repo.fulltext_search = AsyncMock(side_effect=RuntimeError("db down"))
        service = _make_service(entity_repo=entity_repo)

        result = await service._fulltext_fallback(
            question="anything", accessible_ids=[1], max_results=10
        )
        assert result == []



class TestParameterHelpers:
    def test_clamp_results_bounds(self):
        settings = KnowledgeGraphSettings(query_max_results=50)
        service = _make_service(settings=settings)
        assert service._clamp_results(0) == 1
        assert service._clamp_results(25) == 25
        assert service._clamp_results(9999) == 50

    def test_read_canonical_name_normalizes_whitespace_and_case(self):
        assert GraphQueryService._read_canonical_name(
            {"entity_name": "  Bob   Smith "}, "entity_name"
        ) == "bob smith"

    def test_read_canonical_name_missing_raises(self):
        with pytest.raises(_GraphIntentParameterError):
            GraphQueryService._read_canonical_name({"entity_name": "   "}, "entity_name")

    def test_read_optional_entity_type(self):
        assert GraphQueryService._read_optional_entity_type({"t": "person"}, "t") == EntityType.PERSON
        assert GraphQueryService._read_optional_entity_type({"t": ""}, "t") is None
        assert GraphQueryService._read_optional_entity_type({"t": "alien"}, "t") == EntityType.OTHER

    def test_read_required_entity_type_missing_raises(self):
        with pytest.raises(_GraphIntentParameterError):
            GraphQueryService._read_required_entity_type({}, "entity_type")

    def test_read_int_clamps_and_defaults(self):
        assert GraphQueryService._read_int({"d": 5}, "d", default=1, min_value=1, max_value=3) == 3
        assert GraphQueryService._read_int({"d": 0}, "d", default=1, min_value=1, max_value=3) == 1
        assert GraphQueryService._read_int({"d": "x"}, "d", default=2, min_value=1, max_value=3) == 2
        assert GraphQueryService._read_int({}, "d", default=2, min_value=1, max_value=3) == 2

    def test_read_optional_relation_types(self):
        assert GraphQueryService._read_optional_relation_types({"r": None}, "r") is None
        assert GraphQueryService._read_optional_relation_types({"r": "not-a-list"}, "r") is None
        result = GraphQueryService._read_optional_relation_types(
            {"r": ["works_for", "", "located_in"]}, "r"
        )
        assert result is not None and len(result) == 2


class TestMergeLlmParameterAliases:
    def test_find_entity_copies_name_and_type_aliases(self):
        merged = GraphQueryService._merge_llm_parameter_aliases(
            QueryIntent.FIND_ENTITY, {"name": "Bob", "type": "person"}
        )
        assert merged["entity_name"] == "Bob"
        assert merged["entity_type"] == "person"

    def test_existing_value_is_not_overwritten_by_alias(self):
        merged = GraphQueryService._merge_llm_parameter_aliases(
            QueryIntent.FIND_ENTITY, {"entity_name": "Alice", "name": "Bob"}
        )
        assert merged["entity_name"] == "Alice"

    def test_find_path_copies_source_aliases(self):
        merged = GraphQueryService._merge_llm_parameter_aliases(
            QueryIntent.FIND_PATH, {"source": "Bob", "from_type": "person"}
        )
        assert merged["source_name"] == "Bob"
        assert merged["source_type"] == "person"

    def test_list_by_document_copies_doc_id(self):
        merged = GraphQueryService._merge_llm_parameter_aliases(
            QueryIntent.LIST_BY_DOCUMENT, {"doc_id": 7}
        )
        assert merged["document_id"] == 7


class TestBuildNodes:
    def test_dedups_entities_and_adds_relation_endpoints(self):
        entities = [_entity("bob"), _entity("bob")]
        relations = [_relation("bob", "acme")]
        nodes = GraphQueryService._build_nodes(entities, relations)

        names = sorted(n.canonical_name for n in nodes)
        assert names == ["acme", "bob"]


class TestBuildInterpretedAs:
    def test_unknown_intent_returns_none(self):
        assert GraphQueryService._build_interpreted_as(QueryIntent.UNKNOWN, {}) is None

    def test_extracts_typed_fields(self):
        interpreted = GraphQueryService._build_interpreted_as(
            QueryIntent.FIND_NEIGHBORS,
            {
                "entity_name": " Bob ",
                "depth": "2",
                "relation_types": ["works_for", "  "],
                "document_id": "bad",
            },
        )
        assert interpreted is not None
        assert interpreted.entity_name == "Bob"
        assert interpreted.depth == 2
        assert interpreted.relation_types == ["works_for"]
        assert interpreted.document_id is None
