from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.document_collection_users.models import UserInDocumentCollection
from core.integrations.user_profile_client import UserProfile


class UserInDocumentCollectionResponse(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = UserInDocumentCollection
        fields = [
            "id",
            "created_by",
            "created_at",
            "user",
        ]

    def get_user(self, obj: UserInDocumentCollection) -> dict[str, Any]:
        profiles: dict[int, UserProfile] = self.context.get("profiles") or {}
        profile = profiles.get(obj.user_id) or UserProfile(
            id=obj.user_id,
            email="",
            username="",
        )
        return {
            "id": profile.id,
            "email": profile.email,
            "username": profile.username,
        }
