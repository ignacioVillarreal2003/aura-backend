from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import ENUM

from app.domain.constants.document_status import DocumentStatus
from app.domain.constants.document_type import DocumentType
from app.domain.models.base import Base


class Document(Base):
    __tablename__ = "document"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    name = Column(
        String(255),
        nullable=False
    )
    type = Column(
        ENUM(DocumentType, name="document_type", create_type=False),
        nullable=False
    )
    status = Column(
        ENUM(DocumentStatus, name="document_status", create_type=False),
        default=DocumentStatus.pending,
        nullable=False
    )
    path = Column(
        String(255),
        nullable=True
    )

    text_cleaner_type = Column(
        String(255),
        nullable=True
    )
    text_splitter_type = Column(
        String(255),
        nullable=True
    )
    embedder_type = Column(
        String(255),
        nullable=True
    )
    split_size = Column(
        Integer,
        nullable=True
    )
    split_overlap = Column(
        Integer,
        nullable=True
    )

    created_by = Column(
        Integer,
        nullable=False
    )
    created_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False
    )
    updated_by = Column(
        Integer,
        nullable=True
    )
    updated_at = Column(
        DateTime,
        nullable=True
    )
    deleted_by = Column(
        Integer,
        nullable=True
    )
    deleted_at = Column(
        DateTime,
        nullable=True
    )
