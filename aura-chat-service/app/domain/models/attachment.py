from datetime import datetime
from typing import TYPE_CHECKING, Optional
import enum
import uuid

from sqlalchemy import String, Text, BigInteger, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.domain.models.base import Base

if TYPE_CHECKING:
    from app.domain.models.message import Message


class AttachmentType(enum.Enum):
    """Type of attachment."""
    image = "image"
    file = "file"
    audio = "audio"
    video = "video"


class Attachment(Base):
    """
    Represents a file attachment to a message.
    
    Attachments are stored in object storage (MinIO/S3) and referenced here.
    """
    __tablename__ = "attachment"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Foreign key
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("message.id", ondelete="CASCADE"),
        nullable=False
    )

    # File information
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[AttachmentType] = mapped_column(
        Enum(AttachmentType),
        nullable=False
    )
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)

    # Additional metadata
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # AI-generated description
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationships
    message: Mapped["Message"] = relationship(
        "Message",
        back_populates="attachments"
    )

    def __repr__(self) -> str:
        return f"<Attachment(id={self.id}, file_name={self.file_name})>"

    @property
    def is_deleted(self) -> bool:
        """Check if the attachment is soft-deleted."""
        return self.deleted_at is not None


