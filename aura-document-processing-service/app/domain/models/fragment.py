from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.sql import func
from sqlalchemy import Column, Integer, DateTime, Text, ForeignKey, BigInteger

from app.domain.models.base import Base
from app.domain.settings.fragment_settings import FragmentSettings

_fragment_settings = FragmentSettings()


class Fragment(Base):
    __tablename__ = "fragment_controllers"

    id = Column(
        BigInteger,
        primary_key=True,
        index=True
    )

    document_id = Column(
        BigInteger,
        ForeignKey(
            "document_controllers.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    content = Column(
        Text,
        nullable=False
    )
    vector = Column(
        VECTOR(
            dim=_fragment_settings.vector_dimension
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
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_by = Column(
        BigInteger,
        nullable=True
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=True
    )
    deleted_by = Column(
        BigInteger,
        nullable=True
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True
    )
