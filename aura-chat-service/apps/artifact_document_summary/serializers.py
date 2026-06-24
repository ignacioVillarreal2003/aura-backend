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
    retrieve_context = serializers.BooleanField(
        required=False,
        allow_null=True,
        default=None,
        help_text="Recuperar contexto de la base de conocimiento. Si se omite, usa el default del servicio.",
    )
    process_documents = serializers.BooleanField(
        required=False,
        allow_null=True,
        default=None,
        help_text="Procesar el contenido completo de los documentos adjuntos. Si se omite, usa el default del servicio.",
    )


class DocumentSummaryResponse(serializers.ModelSerializer):
    source_chat_id = serializers.SerializerMethodField()

    class Meta:
        model = ArtifactDocumentSummary
        fields = [
            "id",
            "artifact_id",
            "title",
            "description",
            "summary",
            "source_chat_id",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields

    def get_source_chat_id(self, obj) -> int | None:
        return obj.artifact.source_chat_id if obj.artifact_id else None


class DocumentSummaryGenerateResponse(serializers.Serializer):
    document_summary = serializers.SerializerMethodField()
    fragments = _FragmentSerializer(many=True)

    def get_document_summary(self, obj):
        return DocumentSummaryResponse(obj["document_summary"]).data


class DocumentSummaryListResponse(serializers.ModelSerializer):
    source_chat_id = serializers.SerializerMethodField()

    class Meta:
        model = ArtifactDocumentSummary
        fields = [
            "id",
            "artifact_id",
            "title",
            "source_chat_id",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields

    def get_source_chat_id(self, obj) -> int | None:
        return obj.artifact.source_chat_id if obj.artifact_id else None
