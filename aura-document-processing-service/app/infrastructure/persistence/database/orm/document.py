from datetime import datetime
from sqlalchemy import BigInteger, String, DateTime, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.domain.constants.processing_status import ProcessingStatus
from app.domain.field_limits import MAX_STORAGE_URL_CHARS, MAX_NAME_CHARS
from app.infrastructure.persistence.database.orm.base import Base


class Document(Base):
    __tablename__ = "document"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)

    chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)

    name: Mapped[str] = mapped_column(String(MAX_NAME_CHARS), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, server_default="uploaded")

    storage_url: Mapped[str] = mapped_column(String(MAX_STORAGE_URL_CHARS), nullable=False)

    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)

    text_cleaner_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text_splitter_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    embedder_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    split_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    split_overlap: Mapped[int | None] = mapped_column(Integer, nullable=True)

    enrichment_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=ProcessingStatus.pending.value
    )
    graph_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=ProcessingStatus.pending.value
    )

    processing_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processing_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
