from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.sql import func
from sqlalchemy import Column, Integer, DateTime, Text, ForeignKey, BigInteger

from app.configuration.environment_variables import environment_variables
from app.domain.models.base import Base


class Fragment(Base):
    __tablename__ = "fragment"

    id = Column(
        BigInteger,
        primary_key=True,
        index=True
    )

    document_id = Column(
        BigInteger,
        ForeignKey(
            "document.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    content = Column(
        Text,
        nullable=False
    )
    cleaned_content = Column(
        Text,
        nullable=False
    )
    character_count = Column(
        Integer,
        nullable=False
    )
    vector = Column(
        VECTOR(
            dim=environment_variables.vector_dimension
        ),
        nullable=False
    )
    fragment_index = Column(
        Integer,
        nullable=False
    )

    summary = Column(
        Text,
        nullable=True
    )
    entities = Column(
        JSONB,
        nullable=True
    )
    topics = Column(
        ARRAY(Text),
        nullable=True
    )

    created_by = Column(
        BigInteger,
        nullable=False
    )
    created_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False
    )
    deleted_by = Column(
        BigInteger,
        nullable=True
    )
    deleted_at = Column(
        DateTime,
        nullable=True
    )
