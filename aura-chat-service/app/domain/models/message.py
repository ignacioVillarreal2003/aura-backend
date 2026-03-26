from datetime import datetime
from typing import TYPE_CHECKING, Optional
import enum

from sqlalchemy import BigInteger, Text, DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.domain.models.base import Base

if TYPE_CHECKING:
    from app.domain.models.conversation import Chat


class SenderType(enum.Enum):
    system = "system"
    user = "user"


class ChatMessage(Base):
    __tablename__ = "chat_message"

    #Columnas
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chat.id"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    sender_type: Mapped[SenderType] = mapped_column(Enum(SenderType, name="chat_message_sender_type"), nullable=False)
    status: Mapped[MessageStatus] = mapped_column(Enum(MessageStatus, name="chat_message_status"), nullable=False)

    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    #Relaciones
    chat: Mapped["Chat"] = relationship("Chat", back_populates="messages")

    #Métodos

    #Print
    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, chat_id={self.chat_id}, sender_type={self.sender_type.value})>"

    ### DE ACA PARA ABAJO CHECKEAR SI SE VA A PODER BORRAR MENSAJES ###

    #Propiedad
    #Devuelve si esta borrado o no, si tiene fecha de borrado, entonces esta eliminado
    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    #Soft delete del mensaje, se guarda la fecha y usuario q lo borro
    def soft_delete(self, deleted_by: int) -> None:
        self.deleted_at = datetime.utcnow()
        self.deleted_by = deleted_by
