from datetime import datetime
from typing import TYPE_CHECKING, Optional
import enum
import uuid

from sqlalchemy import String, Text, Integer, DateTime, Enum, BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.domain.models.base import Base

if TYPE_CHECKING:
    from app.domain.models.message import Message


class ConversationStatus(enum.Enum):
    """Status of a conversation."""
    active = "active"
    archived = "archived"


class Conversation(Base):
    """
    Represents a chat conversation/thread.
    
    A conversation belongs to a single user and contains multiple messages.
    """
    __tablename__ = "conversation"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Conversation data
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(100), default="default", nullable=False)
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus),
        default=ConversationStatus.active,
        nullable=False
    )

    # Extensible metadata
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Denormalized counters
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Owner
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationships
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        order_by="Message.sequence_number",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, title={self.title}, user_id={self.user_id})>"

    @property
    def is_deleted(self) -> bool:
        """Check if the conversation is soft-deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Mark the conversation as deleted."""
        self.deleted_at = datetime.utcnow()


