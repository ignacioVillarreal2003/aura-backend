import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.infrastructure.persistence.database.database_manager.interfaces.database_manager_interface import (
    DatabaseManagerInterface,
)
from app.infrastructure.persistence.database.repositories.exceptions.database_exceptions import DatabaseException
from app.infrastructure.persistence.database.schema_alignment.exceptions.fragment_vector_schema_aligner_exception import (
    FragmentVectorSchemaAlignerException,
)
from app.infrastructure.persistence.database.schema_alignment.interfaces.fragment_vector_schema_aligner_interface import (
    FragmentVectorSchemaAlignerInterface,
)

logger = logging.getLogger(__name__)

_HNSW_INDEX = "idx_fragment_vector_hnsw"
_HNSW_CTX_INDEX = "idx_fragment_ctx_vector_hnsw"
_DIM_CONSTRAINT = "chk_fragment_embedding_dim"

_VECTOR_HNSW_MAX_DIM = 2000
_HALFVEC_HNSW_MAX_DIM = 4000


class FragmentVectorSchemaAligner(FragmentVectorSchemaAlignerInterface):
    def __init__(
            self,
            *,
            database_manager: DatabaseManagerInterface,
            embedder_factory: EmbedderFactory,
    ) -> None:
        self._database_manager = database_manager
        self._embedder_factory = embedder_factory

    async def align_to_active_dimension(self) -> bool:
        target_dim = self._embedder_factory.get_vector_dimension()

        try:
            current_dim = await self._read_current_dimension()
        except DatabaseException as e:
            raise FragmentVectorSchemaAlignerException(
                "Failed to read the current fragment vector dimension."
            ) from e

        if current_dim == target_dim:
            logger.info(
                "The fragment vector schema already matches the active embedding dimension.",
                extra={"dimension": target_dim},
            )
            return False

        logger.warning(
            "The fragment vector schema does not match the active embedding dimension; migrating.",
            extra={"current_dimension": current_dim, "target_dimension": target_dim},
        )

        try:
            await self._migrate_dimension(target_dim=target_dim)
        except DatabaseException as e:
            raise FragmentVectorSchemaAlignerException(
                "Failed to migrate the fragment vector schema to the active embedding dimension."
            ) from e

        logger.warning(
            "The fragment vector schema was migrated; all fragment vectors were cleared and require re-embedding.",
            extra={"current_dimension": current_dim, "target_dimension": target_dim},
        )
        return True

    async def _read_current_dimension(self) -> int:
        async def _operation(session: AsyncSession) -> int:
            result = await session.execute(
                text(
                    "SELECT atttypmod FROM pg_attribute "
                    "WHERE attrelid = 'fragment'::regclass "
                    "AND attname = 'vector' AND NOT attisdropped"
                )
            )
            value = result.scalar()
            if value is None:
                raise FragmentVectorSchemaAlignerException(
                    "The fragment.vector column could not be found."
                )
            return int(value)

        return await self._database_manager.run_write_transaction_with_retry(
            _operation,
            operation_name="fragment_vector_schema.read_dimension",
        )

    async def _migrate_dimension(self, *, target_dim: int) -> None:
        dim = int(target_dim)
        column_type = "VECTOR" if dim <= _VECTOR_HNSW_MAX_DIM else "HALFVEC"
        index_ops = "vector_cosine_ops" if dim <= _VECTOR_HNSW_MAX_DIM else "halfvec_cosine_ops"

        statements = [
            f"DROP INDEX IF EXISTS {_HNSW_INDEX}",
            f"DROP INDEX IF EXISTS {_HNSW_CTX_INDEX}",
            f"ALTER TABLE fragment DROP CONSTRAINT IF EXISTS {_DIM_CONSTRAINT}",
            "ALTER TABLE fragment ALTER COLUMN vector DROP NOT NULL",
            (
                "UPDATE fragment SET vector = NULL, contextualized_vector = NULL, "
                f"embedding_dim = {dim} "
                f"WHERE embedding_dim <> {dim} OR vector IS NOT NULL "
                "OR contextualized_vector IS NOT NULL"
            ),
            (
                f"ALTER TABLE fragment ALTER COLUMN vector TYPE {column_type}({dim}) "
                f"USING vector::{column_type}({dim})"
            ),
            (
                f"ALTER TABLE fragment ALTER COLUMN contextualized_vector TYPE {column_type}({dim}) "
                f"USING contextualized_vector::{column_type}({dim})"
            ),
            (
                f"ALTER TABLE fragment ADD CONSTRAINT {_DIM_CONSTRAINT} "
                f"CHECK (embedding_dim = {dim})"
            ),
        ]

        if dim <= _HALFVEC_HNSW_MAX_DIM:
            statements.extend(
                [
                    (
                        f"CREATE INDEX {_HNSW_INDEX} ON fragment "
                        f"USING hnsw (vector {index_ops}) "
                        "WITH (m = 16, ef_construction = 64) "
                        "WHERE (deleted_at IS NULL)"
                    ),
                    (
                        f"CREATE INDEX {_HNSW_CTX_INDEX} ON fragment "
                        f"USING hnsw (contextualized_vector {index_ops}) "
                        "WITH (m = 16, ef_construction = 64) "
                        "WHERE (deleted_at IS NULL AND contextualized_vector IS NOT NULL)"
                    ),
                ]
            )
        else:
            logger.warning(
                "The active embedding dimension exceeds the HNSW indexable limit; "
                "vector search will fall back to sequential scan.",
                extra={"target_dimension": dim, "hnsw_max_dimension": _HALFVEC_HNSW_MAX_DIM},
            )

        async def _operation(session: AsyncSession) -> None:
            for statement in statements:
                await session.execute(text(statement))

        await self._database_manager.run_write_transaction_with_retry(
            _operation,
            operation_name="fragment_vector_schema.migrate_dimension",
        )
