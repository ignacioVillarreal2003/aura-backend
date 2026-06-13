from functools import lru_cache
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.sql import func
from sqlalchemy import Column, Integer, DateTime, Text, ForeignKey, BigInteger, String

from app.application.processors.embedders.embedder_settings import EmbedderSettings
from app.domain.constants.processing_status import ProcessingStatus
from app.infrastructure.persistence.database.orm.base import Base


@lru_cache(maxsize=1)
def _get_vector_dimension() -> int:
    return EmbedderSettings().vector_dimension


class Fragment(Base):
    __tablename__ = "fragment"

    id = Column(BigInteger, primary_key=True, index=True)

    document_id = Column(
        BigInteger,
        ForeignKey(
            "document.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    content = Column(Text, nullable=False)
    vector = Column(VECTOR(dim=_get_vector_dimension()), nullable=False)
    fragment_index = Column(Integer, nullable=False)

    summary = Column(Text, nullable=True)
    entities = Column(JSONB, nullable=True)
    topics = Column(ARRAY(Text), nullable=True)

    enrichment_status = Column(
        String(32), nullable=False, server_default=ProcessingStatus.pending.value
    )

    created_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_by = Column(BigInteger, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(BigInteger, nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
