import logging
from typing import Optional
from django.db.models import QuerySet
from django.utils import timezone

from apps.assistant.models import Assistant

logger = logging.getLogger(__name__)


class AssistantRepository:
    def create(
            self,
            *,
            user_id: int,
            name: str,
            description: str,
            system_prompt: str,
            avatar_emoji: str,
            is_active: bool,
            response_style: str = "",
    ) -> Assistant:
        return Assistant.objects.create(
            created_by=user_id,
            name=name,
            description=description,
            system_prompt=system_prompt,
            response_style=response_style,
            avatar_emoji=avatar_emoji,
            is_active=is_active,
        )

    def get_by_id(self, assistant_id: int) -> Optional[Assistant]:
        return Assistant.objects.filter(id=assistant_id).first()

    def get_by_id_for_update(self, assistant_id: int) -> Optional[Assistant]:
        return Assistant.objects.select_for_update().filter(id=assistant_id).first()

    def exists_with_name(self, name: str) -> bool:
        return Assistant.objects.filter(name=name).exists()

    def list_active(self, search: Optional[str] = None) -> QuerySet[Assistant]:
        qs = Assistant.objects.filter(is_active=True)
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def list_all(self, search: Optional[str] = None) -> QuerySet[Assistant]:
        qs = Assistant.objects.all()
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def update(
            self,
            assistant: Assistant,
            *,
            name: Optional[str] = None,
            description: Optional[str] = None,
            system_prompt: Optional[str] = None,
            response_style: Optional[str] = None,
            avatar_emoji: Optional[str] = None,
            is_active: Optional[bool] = None,
            updated_by: int,
    ) -> Assistant:
        update_fields = ["updated_by", "updated_at"]
        assistant.updated_by = updated_by

        if name is not None:
            assistant.name = name
            update_fields.append("name")
        if description is not None:
            assistant.description = description
            update_fields.append("description")
        if system_prompt is not None:
            assistant.system_prompt = system_prompt
            update_fields.append("system_prompt")
        if response_style is not None:
            assistant.response_style = response_style
            update_fields.append("response_style")
        if avatar_emoji is not None:
            assistant.avatar_emoji = avatar_emoji
            update_fields.append("avatar_emoji")
        if is_active is not None:
            assistant.is_active = is_active
            update_fields.append("is_active")

        assistant.updated_at = timezone.now()
        assistant.save(update_fields=update_fields)
        return assistant

    def soft_delete(self, assistant: Assistant, deleted_by: int) -> None:
        assistant.delete(deleted_by=deleted_by)


assistant_repository = AssistantRepository()
