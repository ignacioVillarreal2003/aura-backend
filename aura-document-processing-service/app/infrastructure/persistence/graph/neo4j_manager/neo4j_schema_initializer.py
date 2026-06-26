import logging
from neo4j import AsyncDriver
from neo4j.exceptions import Neo4jError

from app.infrastructure.persistence.graph.neo4j_manager.exceptions.neo4j_manager_exception import (
    Neo4jSchemaInitializationException,
)

logger = logging.getLogger(__name__)

_SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE CONSTRAINT entity_unique IF NOT EXISTS
    FOR (e:Entity) REQUIRE (e.canonical_name, e.type) IS UNIQUE
    """,
    """
    CREATE INDEX entity_canonical_name IF NOT EXISTS
        FOR (e:Entity) ON (e.canonical_name)
    """,
    """
    CREATE INDEX entity_type IF NOT EXISTS
        FOR (e:Entity) ON (e.type)
    """,
    """
    CREATE INDEX entity_display_name IF NOT EXISTS
        FOR (e:Entity) ON (e.display_name)
    """,
    """
    CREATE INDEX rel_type IF NOT EXISTS
        FOR ()-[r:REL]-() ON (r.type)
    """,
    """
    CREATE FULLTEXT INDEX entity_fulltext IF NOT EXISTS
    FOR (n:Entity)
    ON EACH [n.canonical_name, n.display_name, n.aliases]
    """,
    """
    CREATE INDEX rel_confidence IF NOT EXISTS
        FOR ()-[r:REL]-() ON (r.confidence)
    """,
    """
    CREATE INDEX rel_type_confidence IF NOT EXISTS
        FOR ()-[r:REL]-() ON (r.type, r.confidence)
    """,
)


class Neo4jSchemaInitializer:
    def __init__(self, driver: AsyncDriver, database: str) -> None:
        self._driver = driver
        self._database = database

    async def initialize(self) -> None:
        logger.info(
            "Applying knowledge graph schema (constraints and indexes).",
            extra={"database": self._database, "statements": len(_SCHEMA_STATEMENTS)},
        )
        async with self._driver.session(database=self._database) as session:
            for statement in _SCHEMA_STATEMENTS:
                try:
                    await session.run(statement)
                except Neo4jError as e:
                    logger.exception(
                        "Failed to apply a schema statement.",
                        extra={
                            "database": self._database,
                            "neo4j_code": getattr(e, "code", None),
                        },
                    )
                    raise Neo4jSchemaInitializationException(
                        "Failed to apply the knowledge graph schema."
                    ) from e
                except Exception as e:
                    logger.exception(
                        "Unexpected error while applying a schema statement.",
                        extra={"database": self._database},
                    )
                    raise Neo4jSchemaInitializationException(
                        "Unexpected error while applying the knowledge graph schema."
                    ) from e

        logger.info(
            "Knowledge graph schema applied successfully.",
            extra={"database": self._database},
        )
