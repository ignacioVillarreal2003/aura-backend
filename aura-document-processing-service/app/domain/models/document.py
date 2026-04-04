from sqlalchemy import Column, BigInteger, String, DateTime, Text, Integer, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import ENUM

from app.domain.constants.document_status import DocumentStatus
from app.domain.constants.document_mime_type import DocumentMimeType
from app.domain.constants.document_type import DocumentType
from app.domain.models.base import Base


class Document(Base):
    __tablename__ = "document"

    id = Column(
        BigInteger,
        primary_key=True,
        index=True
    )

    chat_id = Column(
        BigInteger,
        ForeignKey(
            "chat.id",
            ondelete="CASCADE"
        ),
        nullable=True
    )

    name = Column(
        String(255),
        nullable=False
    )
    description = Column(
        Text,
        nullable=True
    )
    mime_type = Column(
        ENUM(
            DocumentMimeType,
            name="document_mime_type",
            create_type=False
        ),
        nullable=False
    )
    status = Column(
        ENUM(
            DocumentStatus,
            name="document_status",
            create_type=False
        ),
        default=DocumentStatus.uploaded,
        nullable=False
    )
    storage_url = Column(
        String(255),
        nullable=False
    )

    file_size_bytes = Column(
        BigInteger,
        nullable=False
    )

    type = Column(
        ENUM(
            DocumentType,
            name="document_type",
            create_type=False),
        nullable=True
    )
    category = Column(
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

    processing_started_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    processing_finished_at = Column(
        DateTime(timezone=True),
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
