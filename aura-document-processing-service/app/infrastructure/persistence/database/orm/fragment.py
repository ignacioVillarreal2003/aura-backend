from datetime import datetime
from functools import lru_cache
from typing import Any
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy import Integer, DateTime, Text, ForeignKey, BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.application.processors.embedders.embedder_settings import EmbedderSettings
from app.domain.constants.processing_status import ProcessingStatus
from app.infrastructure.persistence.database.orm.base import Base


@lru_cache(maxsize=1)
def _get_vector_dimension() -> int:
    dimension = EmbedderSettings().vector_dimension
    if dimension is None:
        raise ValueError("The embedder vector dimension could not be resolved.")
    return dimension


class Fragment(Base):
    __tablename__ = "fragment"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)

    document_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "document.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)

    vector: Mapped[Any] = mapped_column(VECTOR(dim=_get_vector_dimension()), nullable=False)

    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_dim: Mapped[int] = mapped_column(Integer, nullable=False)

    embedding_identity: Mapped[str] = mapped_column(Text, nullable=False)

    fragment_index: Mapped[int] = mapped_column(Integer, nullable=False)

    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    contextualized_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    contextualized_vector: Mapped[Any | None] = mapped_column(
        VECTOR(dim=_get_vector_dimension()), nullable=True
    )
    contextualized_embedding_identity: Mapped[str | None] = mapped_column(Text, nullable=True)

    contextualization_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=ProcessingStatus.pending.value
    )

    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
