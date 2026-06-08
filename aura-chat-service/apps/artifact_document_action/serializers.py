from rest_framework import serializers

from apps.artifact.shared_serializers import FragmentSerializer as _FragmentSerializer
from apps.artifact_document_action.models import ArtifactDocumentAction

_ACTION_CHOICES = ["summarize", "essay", "key_points", "compare", "analyze", "explain", "report"]


class GenerateDocumentActionRequest(serializers.Serializer):
    document_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=50,
    )
    instruction = serializers.CharField(allow_blank=False, max_length=10000)
    action = serializers.ChoiceField(choices=_ACTION_CHOICES, required=False, allow_null=True)
    chat_id = serializers.IntegerField()


class DocumentActionResponse(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    source_chat_id = serializers.SerializerMethodField()

    class Meta:
        model = ArtifactDocumentAction
        fields = [
            "id",
            "artifact_id",
            "title",
            "document_ids",
            "instruction",
            "action",
            "result",
            "source_chat_id",
            "created_by",
            "created_at",
            "updated_by",
            "updated_at",
        ]
        read_only_fields = fields

    def get_title(self, obj) -> str:
        return obj.artifact.title if obj.artifact_id else ""

    def get_source_chat_id(self, obj) -> int | None:
        return obj.artifact.source_chat_id if obj.artifact_id else None


class DocumentActionGenerateResponse(serializers.Serializer):
    document_action = serializers.SerializerMethodField()
    fragments = _FragmentSerializer(many=True)

    def get_document_action(self, obj):
        return DocumentActionResponse(obj["document_action"]).data


class UpdateDocumentActionRequest(serializers.Serializer):
    title = serializers.CharField(max_length=500, allow_blank=False, required=False)
    result = serializers.CharField(allow_blank=True, required=False)
    instruction = serializers.CharField(allow_blank=False, max_length=10000, required=False)

    def validate(self, data):
        if not data:
            raise serializers.ValidationError("Se requiere al menos un campo a actualizar.")
        return data


class DocumentActionListResponse(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    source_chat_id = serializers.SerializerMethodField()

    class Meta:
        model = ArtifactDocumentAction
        fields = [
            "id",
            "artifact_id",
            "title",
            "document_ids",
            "instruction",
            "action",
            "source_chat_id",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields

    def get_title(self, obj) -> str:
        return obj.artifact.title if obj.artifact_id else ""

    def get_source_chat_id(self, obj) -> int | None:
        return obj.artifact.source_chat_id if obj.artifact_id else None
