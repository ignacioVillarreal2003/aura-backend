from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.domain.models.base import Base

if TYPE_CHECKING:
    from app.domain.models.message import ChatMessage
    from app.domain.models.chat_membership import ChatMembership


class Chat(Base):
    __tablename__ = "chat"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_style: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="chat",
        order_by="ChatMessage.created_at",
        lazy="selectin"
    )
    memberships: Mapped[list["ChatMembership"]] = relationship(
        "ChatMembership",
        back_populates="chat",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Chat(id={self.id}, name={self.name})>"

    @property
    def is_individual(self) -> bool:
        return len(self.memberships) == 1

    @property
    def is_group(self) -> bool:
        return len(self.memberships) > 1

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self, deleted_by: int) -> None:
        self.deleted_at = datetime.utcnow()
        self.deleted_by = deleted_by
