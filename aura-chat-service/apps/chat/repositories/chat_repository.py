import logging
from django.db.models import Count, DateTimeField, F, IntegerField, Q, QuerySet, Subquery
from django.db.models.expressions import OuterRef
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.chat.models.chat import Chat

logger = logging.getLogger(__name__)

_ORDERING_MAP = {
    "last_message_at": F("last_message_at").asc(nulls_last=True),
    "-last_message_at": F("last_message_at").desc(nulls_last=True),
    "created_at": F("created_at").asc(),
    "-created_at": F("created_at").desc(),
    "name": F("name").asc(),
    "-name": F("name").desc(),
}

ALLOWED_ORDERINGS = frozenset(_ORDERING_MAP.keys())


def _membership_subquery(member_id: int, field: str) -> Subquery:
    from apps.membership.models.chat_membership import ChatMembership

    return Subquery(
        ChatMembership.objects.filter(
            chat_id=OuterRef("pk"),
            member_id=member_id,
            status="active",
            deleted_at__isnull=True,
        ).values(field)[:1],
        output_field=DateTimeField(),
    )


def _member_count_subquery() -> Coalesce:
    from apps.membership.models.chat_membership import ChatMembership

    return Coalesce(
        Subquery(
            ChatMembership.objects.filter(
                chat_id=OuterRef("pk"),
                status="active",
                deleted_at__isnull=True,
            ).values("chat_id").annotate(c=Count("id")).values("c")[:1],
            output_field=IntegerField(),
        ),
        0,
        output_field=IntegerField(),
    )


def _unread_count_subquery(member_id: int) -> Coalesce:
    from apps.artifact.models.artifact import Artifact
    from apps.artifact_message.models import ArtifactMessage
    from apps.membership.models.chat_membership import ChatMembership

    cutoff_sq = Subquery(
        ChatMembership.objects.filter(
            chat_id=OuterRef(OuterRef("pk")),
            member_id=member_id,
            status="active",
            deleted_at__isnull=True,
        ).annotate(
            cutoff=Coalesce("last_read_at", "joined_at"),
        ).values("cutoff")[:1],
        output_field=DateTimeField(),
    )

    return Coalesce(
        Subquery(
            ArtifactMessage.objects.filter(
                artifact__source_chat_id=OuterRef("pk"),
                artifact__type=Artifact.Type.MESSAGE,
                created_at__gt=cutoff_sq,
            ).values("artifact__source_chat_id").annotate(c=Count("id")).values("c")[:1],
            output_field=IntegerField(),
        ),
        0,
        output_field=IntegerField(),
    )


class ChatRepository:
    @staticmethod
    def create(name: str, created_by: int, **kwargs) -> Chat:
        return Chat.objects.create(name=name, created_by=created_by, **kwargs)

    @staticmethod
    def get_by_id(chat_id: int) -> Chat | None:
        try:
            return Chat.objects.get(pk=chat_id)
        except Chat.DoesNotExist:
            return None

    @staticmethod
    def get_by_id_for_update(chat_id: int) -> Chat | None:
        try:
            return Chat.objects.select_for_update().get(pk=chat_id)
        except Chat.DoesNotExist:
            return None

    @staticmethod
    def get_chats_for_member(
            member_id: int,
            search: str | None = None,
            ordering: str = "-last_message_at",
            tags: list[str] | None = None,
    ) -> QuerySet[Chat]:
        order_expr = _ORDERING_MAP.get(ordering, _ORDERING_MAP["-last_message_at"])

        qs = (
            Chat.objects.filter(
                chatmembership__member_id=member_id,
                chatmembership__status="active",
                chatmembership__deleted_at__isnull=True,
                chatmembership__archived_at__isnull=True,
            )
            .annotate(
                member_count=_member_count_subquery(),
                pinned_at=_membership_subquery(member_id, "pinned_at"),
                unread_count=_unread_count_subquery(member_id),
            )
            .distinct()
        )

        if search:
            qs = qs.filter(name__icontains=search)
        if tags:
            qs = qs.filter(tags__contains=tags)

        return qs.order_by(F("pinned_at").desc(nulls_last=True), order_expr)

    @staticmethod
    def get_archived_chats_for_member(
            member_id: int,
            search: str | None = None,
            ordering: str = "-last_message_at",
            tags: list[str] | None = None,
    ) -> QuerySet[Chat]:
        order_expr = _ORDERING_MAP.get(ordering, _ORDERING_MAP["-last_message_at"])

        qs = (
            Chat.objects.filter(
                chatmembership__member_id=member_id,
                chatmembership__status="active",
                chatmembership__deleted_at__isnull=True,
                chatmembership__archived_at__isnull=False,
            )
            .annotate(
                member_count=_member_count_subquery(),
                pinned_at=_membership_subquery(member_id, "pinned_at"),
                archived_at=_membership_subquery(member_id, "archived_at"),
                unread_count=_unread_count_subquery(member_id),
            )
            .distinct()
        )

        if search:
            qs = qs.filter(name__icontains=search)
        if tags:
            qs = qs.filter(tags__contains=tags)

        return qs.order_by(order_expr)

    @staticmethod
    def get_chats_created_by(
            user_id: int,
            search: str | None = None,
            ordering: str = "-created_at",
            tags: list[str] | None = None,
    ) -> QuerySet[Chat]:
        order_expr = _ORDERING_MAP.get(ordering, _ORDERING_MAP["-created_at"])

        qs = (
            Chat.objects.filter(created_by=user_id)
            .annotate(
                member_count=Count(
                    "chatmembership",
                    filter=Q(
                        chatmembership__status="active",
                        chatmembership__deleted_at__isnull=True,
                    ),
                ),
                pinned_at=_membership_subquery(user_id, "pinned_at"),
                unread_count=_unread_count_subquery(user_id),
            )
        )

        if search:
            qs = qs.filter(name__icontains=search)
        if tags:
            qs = qs.filter(tags__contains=tags)

        return qs.order_by(F("pinned_at").desc(nulls_last=True), order_expr)

    @staticmethod
    def list_all(
            search: str | None = None,
            ordering: str = "-created_at",
            tags: list[str] | None = None,
    ) -> QuerySet[Chat]:
        order_expr = _ORDERING_MAP.get(ordering, _ORDERING_MAP["-created_at"])
        qs = Chat.objects.annotate(
            member_count=Count(
                "chatmembership",
                filter=Q(
                    chatmembership__status="active",
                    chatmembership__deleted_at__isnull=True,
                ),
            )
        )
        if search:
            qs = qs.filter(name__icontains=search)
        if tags:
            qs = qs.filter(tags__contains=tags)
        return qs.order_by(order_expr)

    @staticmethod
    def update(chat: Chat, updated_by: int, **fields) -> Chat:
        for key, value in fields.items():
            setattr(chat, key, value)
        chat.updated_by = updated_by
        chat.updated_at = timezone.now()

        update_fields = list(fields.keys()) + ["updated_by", "updated_at"]
        chat.save(update_fields=update_fields)
        return chat

    @staticmethod
    def touch_last_message_at(chat_id: int, updated_by: int) -> None:
        now = timezone.now()
        Chat.objects.filter(pk=chat_id).update(
            last_message_at=now,
            updated_by=updated_by,
            updated_at=now,
        )

    @staticmethod
    def get_latest_by_assistant(user_id: int, assistant_id: int) -> Chat | None:
        return (
            Chat.objects
            .filter(created_by=user_id, source_assistant_id=assistant_id)
            .order_by("-created_at")
            .first()
        )

    @staticmethod
    def soft_delete(chat: Chat, deleted_by: int) -> None:
        chat.delete(deleted_by=deleted_by)


chat_repository = ChatRepository()
