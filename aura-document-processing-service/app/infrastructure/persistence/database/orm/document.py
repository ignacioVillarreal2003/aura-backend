from sqlalchemy import Column, BigInteger, String, DateTime, Text, Integer
from sqlalchemy.sql import func

from app.domain.constants.processing_status import ProcessingStatus
from app.domain.field_limits import MAX_STORAGE_URL_CHARS, MAX_NAME_CHARS
from app.infrastructure.persistence.database.orm.base import Base


class Document(Base):
    __tablename__ = "document"

    id = Column(BigInteger, primary_key=True, index=True)

    # The `chat` table lives in another service's domain; its ORM model is no
    # longer registered in this service's metadata. The foreign key still exists
    # at the database level, but declaring it here makes SQLAlchemy fail to
    # resolve the (absent) `chat` table during flush. Keep it as a plain column.
    chat_id = Column(BigInteger, nullable=True, index=True)

    name = Column(String(MAX_NAME_CHARS), nullable=False)
    description = Column(Text, nullable=True)
    mime_type = Column(String(64), nullable=False)
    status = Column(String(64), nullable=False, server_default="uploaded")

    storage_url = Column(String(MAX_STORAGE_URL_CHARS), nullable=False)

    file_size_bytes = Column(BigInteger, nullable=False)

    type = Column(String(64), nullable=True)
    category = Column(String(255), nullable=True)

    text_cleaner_type = Column(String(255), nullable=True)
    text_splitter_type = Column(String(255), nullable=True)
    embedder_type = Column(String(255), nullable=True)
    split_size = Column(Integer, nullable=True)
    split_overlap = Column(Integer, nullable=True)

    enrichment_status = Column(
        String(32), nullable=False, server_default=ProcessingStatus.pending.value
    )
    graph_status = Column(
        String(32), nullable=False, server_default=ProcessingStatus.pending.value
    )

    processing_started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processing_finished_at = Column(DateTime(timezone=True), nullable=True)

    created_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_by = Column(BigInteger, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(BigInteger, nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
