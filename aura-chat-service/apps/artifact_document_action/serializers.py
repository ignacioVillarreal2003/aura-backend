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


class DocumentActionResponse(serializers.ModelSerializer):
    source_chat_id = serializers.SerializerMethodField()

    class Meta:
        model = ArtifactDocumentAction
        fields = [
            "id",
            "artifact_id",
            "title",
            "description",
            "instruction",
            "action",
            "result",
            "source_chat_id",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields

    def get_source_chat_id(self, obj) -> int | None:
        return obj.artifact.source_chat_id if obj.artifact_id else None


class DocumentActionGenerateResponse(serializers.Serializer):
    document_action = serializers.SerializerMethodField()
    fragments = _FragmentSerializer(many=True)

    def get_document_action(self, obj):
        return DocumentActionResponse(obj["document_action"]).data


class DocumentActionListResponse(serializers.ModelSerializer):
    source_chat_id = serializers.SerializerMethodField()

    class Meta:
        model = ArtifactDocumentAction
        fields = [
            "id",
            "artifact_id",
            "title",
            "instruction",
            "action",
            "source_chat_id",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields

    def get_source_chat_id(self, obj) -> int | None:
        return obj.artifact.source_chat_id if obj.artifact_id else None
