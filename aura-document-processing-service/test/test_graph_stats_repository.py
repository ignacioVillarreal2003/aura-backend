"""
Unit tests for GraphStatsRepository.

These exercise the repository directly against a mocked Neo4j manager. The mock
uses ``spec=Neo4jManagerInterface`` so attributes outside the interface (e.g. a
non-existent ``session()``) raise AttributeError instead of being auto-created;
this is what guards against regressing to the wrong manager API.
"""
from unittest.mock import AsyncMock

import pytest
from neo4j.exceptions import Neo4jError

from app.infrastructure.persistence.graph.neo4j_manager.interfaces.neo4j_manager_interface import (
    Neo4jManagerInterface,
)
from app.infrastructure.persistence.graph.repositories.exceptions.graph_repository_exceptions import (
    GraphPersistenceException,
)
from app.infrastructure.persistence.graph.repositories.graph_stats_repository import (
    GraphStatsRepository,
)


def _manager() -> AsyncMock:
    return AsyncMock(spec=Neo4jManagerInterface)


class TestGraphStatsRepository:
    @pytest.mark.asyncio
    async def test_aggregates_counts_from_execute_read(self):
        manager = _manager()
        manager.execute_read.side_effect = [
            [{"type": "person", "cnt": 3}, {"type": "organization", "cnt": 2}],
            [{"total": 7}],
            [{"total": 4}],
        ]
        repo = GraphStatsRepository(neo4j_manager=manager)

        stats = await repo.get_stats()

        assert stats.total_entities == 5
        assert stats.entities_by_type == {"person": 3, "organization": 2}
        assert stats.total_relations == 7
        assert stats.total_documents_indexed == 4
        assert manager.execute_read.await_count == 3

    @pytest.mark.asyncio
    async def test_uses_execute_read_and_not_session(self):
        manager = _manager()
        manager.execute_read.side_effect = [[], [], []]
        repo = GraphStatsRepository(neo4j_manager=manager)

        await repo.get_stats()

        manager.execute_read.assert_awaited()
        assert not hasattr(manager, "session")

    @pytest.mark.asyncio
    async def test_empty_graph_returns_zeros(self):
        manager = _manager()
        manager.execute_read.side_effect = [[], [], []]
        repo = GraphStatsRepository(neo4j_manager=manager)

        stats = await repo.get_stats()

        assert stats.total_entities == 0
        assert stats.entities_by_type == {}
        assert stats.total_relations == 0
        assert stats.total_documents_indexed == 0

    @pytest.mark.asyncio
    async def test_neo4j_error_is_wrapped(self):
        manager = _manager()
        manager.execute_read.side_effect = Neo4jError("boom")
        repo = GraphStatsRepository(neo4j_manager=manager)

        with pytest.raises(GraphPersistenceException):
            await repo.get_stats()
