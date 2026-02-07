from pgvector.sqlalchemy import VECTOR
from sqlalchemy.sql import func
from sqlalchemy import Column, Integer, DateTime, Text, ForeignKey

from app.configuration.environment_variables import environment_variables
from app.domain.models.base import Base


class Fragment(Base):
    __tablename__ = "fragment"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    document_id = Column(
        Integer,
        ForeignKey(
            "document.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    vector = Column(
        VECTOR(
            dim=environment_variables.vector_dimension
        ),
        nullable=True
    )
    content = Column(
        Text,
        nullable=False
    )
    fragment_index = Column(
        Integer,
        nullable=False
    )

    created_by = Column(
        Integer,
        nullable=False
    )
    created_at = Column(
        DateTime,
        server_default=func.now()
    )
    deleted_by = Column(
        Integer,
        nullable=True
    )
    deleted_at = Column(
        DateTime,
        nullable=True
    )
