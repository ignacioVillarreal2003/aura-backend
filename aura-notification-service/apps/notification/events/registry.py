from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Iterable
from django.conf import settings

from apps.notification.models import NotificationSeverity, PreferenceChannel


class NotificationType:
    SYSTEM = "system"
    ADMIN = "admin"
    EVENT = "event"


class EventType:
    CHAT_MEMBER_INVITED = "chat.member.invited"
    CHAT_MEMBER_REMOVED = "chat.member.removed"
    CHAT_LOCKED = "chat.locked"

    AUTH_PASSWORD_CHANGED = "auth.password.changed"
    AUTH_NEW_LOGIN = "auth.new_login"

    DOCUMENT_PROCESSING_DONE = "document.processing.done"
    DOCUMENT_PROCESSING_FAILED = "document.processing.failed"

    ADMIN_BROADCAST = "admin.broadcast"
    SYSTEM_ANNOUNCEMENT = "system.announcement"


def _default_link(_context: dict) -> str | None:
    return None


def _chat_link(context: dict) -> str | None:
    chat_id = context.get("chat_id")
    if not chat_id:
        return None
    base = settings.NOTIFICATION_DEFAULT_LINK_BASE_URL.rstrip("/")
    return f"{base}/chats/{chat_id}"


def _document_link(context: dict) -> str | None:
    document_id = context.get("document_id")
    if not document_id:
        return None
    base = settings.NOTIFICATION_DEFAULT_LINK_BASE_URL.rstrip("/")
    return f"{base}/documents/{document_id}"


@dataclass(frozen=True)
class EventDefinition:
    event_type: str
    type: str
    severity: str
    description: str
    default_channels: tuple[str, ...]
    template_id: str
    is_silenceable: bool = True
    available_channels: tuple[str, ...] = (
        PreferenceChannel.INAPP,
        PreferenceChannel.EMAIL,
    )
    link_builder: Callable[[dict], str | None] = field(default=_default_link)

    def has_channel(self, channel: str) -> bool:
        return channel in self.default_channels

    def to_public_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "type": self.type,
            "severity": self.severity,
            "description": self.description,
            "default_channels": list(self.default_channels),
            "available_channels": list(self.available_channels),
            "is_silenceable": self.is_silenceable,
        }


_EVENTS: dict[str, EventDefinition] = {
    EventType.CHAT_MEMBER_INVITED: EventDefinition(
        event_type=EventType.CHAT_MEMBER_INVITED,
        type=NotificationType.EVENT,
        severity=NotificationSeverity.INFO,
        description="Te invitaron a un chat.",
        default_channels=(PreferenceChannel.INAPP,),
        template_id="chat_member_invited",
        link_builder=_chat_link,
    ),
    EventType.CHAT_MEMBER_REMOVED: EventDefinition(
        event_type=EventType.CHAT_MEMBER_REMOVED,
        type=NotificationType.EVENT,
        severity=NotificationSeverity.WARNING,
        description="Te quitaron de un chat.",
        default_channels=(PreferenceChannel.INAPP,),
        template_id="chat_member_removed",
        link_builder=_chat_link,
    ),
    EventType.CHAT_LOCKED: EventDefinition(
        event_type=EventType.CHAT_LOCKED,
        type=NotificationType.EVENT,
        severity=NotificationSeverity.WARNING,
        description="Un chat fue bloqueado.",
        default_channels=(PreferenceChannel.INAPP,),
        template_id="chat_locked",
        link_builder=_chat_link,
    ),
    EventType.AUTH_PASSWORD_CHANGED: EventDefinition(
        event_type=EventType.AUTH_PASSWORD_CHANGED,
        type=NotificationType.SYSTEM,
        severity=NotificationSeverity.CRITICAL,
        description="Cambio de contrasena exitoso.",
        default_channels=(PreferenceChannel.INAPP, PreferenceChannel.EMAIL),
        template_id="auth_password_changed",
        is_silenceable=False,
    ),
    EventType.AUTH_NEW_LOGIN: EventDefinition(
        event_type=EventType.AUTH_NEW_LOGIN,
        type=NotificationType.SYSTEM,
        severity=NotificationSeverity.WARNING,
        description="Inicio de sesion desde un dispositivo nuevo.",
        default_channels=(PreferenceChannel.INAPP, PreferenceChannel.EMAIL),
        template_id="auth_new_login",
    ),
    EventType.DOCUMENT_PROCESSING_DONE: EventDefinition(
        event_type=EventType.DOCUMENT_PROCESSING_DONE,
        type=NotificationType.EVENT,
        severity=NotificationSeverity.SUCCESS,
        description="Tu documento termino de procesarse.",
        default_channels=(PreferenceChannel.INAPP,),
        template_id="document_processing_done",
        link_builder=_document_link,
    ),
    EventType.DOCUMENT_PROCESSING_FAILED: EventDefinition(
        event_type=EventType.DOCUMENT_PROCESSING_FAILED,
        type=NotificationType.EVENT,
        severity=NotificationSeverity.CRITICAL,
        description="El procesamiento de tu documento fallo.",
        default_channels=(PreferenceChannel.INAPP, PreferenceChannel.EMAIL),
        template_id="document_processing_failed",
        link_builder=_document_link,
    ),
    EventType.ADMIN_BROADCAST: EventDefinition(
        event_type=EventType.ADMIN_BROADCAST,
        type=NotificationType.ADMIN,
        severity=NotificationSeverity.INFO,
        description="Mensaje de un administrador.",
        default_channels=(PreferenceChannel.INAPP,),
        template_id="admin_broadcast",
    ),
    EventType.SYSTEM_ANNOUNCEMENT: EventDefinition(
        event_type=EventType.SYSTEM_ANNOUNCEMENT,
        type=NotificationType.SYSTEM,
        severity=NotificationSeverity.INFO,
        description="Anuncio del sistema.",
        default_channels=(PreferenceChannel.INAPP,),
        template_id="system_announcement",
        is_silenceable=False,
    ),
}


def get_event(event_type: str) -> EventDefinition:
    try:
        return _EVENTS[event_type]
    except KeyError as exc:
        raise KeyError(f"Unknown event_type '{event_type}'.") from exc


def is_known_event(event_type: str) -> bool:
    return event_type in _EVENTS


def iter_events() -> Iterable[EventDefinition]:
    return _EVENTS.values()
