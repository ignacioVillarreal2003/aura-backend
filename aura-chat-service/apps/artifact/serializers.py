from rest_framework import serializers

from apps.artifact.models import Artifact, ArtifactVersion
from apps.artifact.registry import ARTIFACT_TYPES


class ArtifactResponse(serializers.ModelSerializer):
    class Meta:
        model = Artifact
        fields = [
            "id",
            "type",
            "title",
            "description",
            "status",
            "version",
            "mode",
            "fragments",
            "source_chat_id",
            "created_by",
            "created_at",
            "updated_by",
            "updated_at",
        ]
        read_only_fields = fields


class ArtifactListResponse(serializers.ModelSerializer):
    class Meta:
        model = Artifact
        fields = [
            "id",
            "type",
            "title",
            "status",
            "version",
            "mode",
            "source_chat_id",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields


class ArtifactVersionResponse(serializers.ModelSerializer):
    class Meta:
        model = ArtifactVersion
        fields = [
            "id",
            "artifact_id",
            "version_number",
            "title",
            "description",
            "status",
            "mode",
            "change_summary",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields


class CreateArtifactRequest(serializers.Serializer):
    type = serializers.ChoiceField(choices=sorted(ARTIFACT_TYPES))
    source_chat_id = serializers.IntegerField()
    title = serializers.CharField(max_length=500, allow_blank=True, default="")
    description = serializers.CharField(required=False, allow_blank=True, default="")
    status = serializers.ChoiceField(choices=Artifact.Status.choices, required=False)
    mode = serializers.ChoiceField(choices=Artifact.Mode.choices, required=False, default=Artifact.Mode.DIRECT)


class UpdateArtifactRequest(serializers.Serializer):
    title = serializers.CharField(max_length=500, allow_blank=False, required=False)
    description = serializers.CharField(allow_blank=True, required=False)
    status = serializers.ChoiceField(choices=Artifact.Status.choices, required=False)
    mode = serializers.ChoiceField(choices=Artifact.Mode.choices, required=False)
    change_summary = serializers.CharField(allow_blank=True, required=False, default="")

    def validate(self, data):
        if not any(k in data for k in ("title", "description", "status", "mode")):
            raise serializers.ValidationError("Se requiere al menos un campo a actualizar.")
        return data
