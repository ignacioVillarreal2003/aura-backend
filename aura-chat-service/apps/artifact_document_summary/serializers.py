from rest_framework import serializers

from apps.artifact.shared_serializers import FragmentSerializer as _FragmentSerializer
from apps.artifact_document_summary.models import ArtifactDocumentSummary


class GenerateDocumentSummaryRequest(serializers.Serializer):
    document_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=50,
    )
    chat_id = serializers.IntegerField()


class DocumentSummaryResponse(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    source_chat_id = serializers.SerializerMethodField()

    class Meta:
        model = ArtifactDocumentSummary
        fields = [
            "id",
            "artifact_id",
            "title",
            "document_ids",
            "summary",
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


class DocumentSummaryGenerateResponse(serializers.Serializer):
    document_summary = serializers.SerializerMethodField()
    fragments = _FragmentSerializer(many=True)

    def get_document_summary(self, obj):
        return DocumentSummaryResponse(obj["document_summary"]).data


class UpdateDocumentSummaryRequest(serializers.Serializer):
    title = serializers.CharField(max_length=500, allow_blank=False, required=False)
    summary = serializers.CharField(allow_blank=True, required=False)

    def validate(self, data):
        if not data:
            raise serializers.ValidationError("Se requiere al menos un campo a actualizar.")
        return data


class DocumentSummaryListResponse(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    source_chat_id = serializers.SerializerMethodField()

    class Meta:
        model = ArtifactDocumentSummary
        fields = [
            "id",
            "artifact_id",
            "title",
            "document_ids",
            "source_chat_id",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields

    def get_title(self, obj) -> str:
        return obj.artifact.title if obj.artifact_id else ""

    def get_source_chat_id(self, obj) -> int | None:
        return obj.artifact.source_chat_id if obj.artifact_id else None
