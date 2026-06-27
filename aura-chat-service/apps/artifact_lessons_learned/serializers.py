from rest_framework import serializers

from apps.artifact.shared_serializers import FragmentSerializer as _FragmentSerializer, \
    MessageSerializer as _MessageSerializer
from apps.artifact_lessons_learned.models import ArtifactLessonsLearned, ArtifactLessonsLearnedItem
from core.validators.audio import MAX_AUDIO_MB as _MAX_AUDIO_MB, SUPPORTED_AUDIO_TYPES as _SUPPORTED_AUDIO_TYPES


class GenerateLessonsLearnedRequest(serializers.Serializer):
    message = serializers.CharField(allow_blank=True, max_length=4000, required=False)
    audio = serializers.FileField(required=False)
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
    document_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        default=list,
        max_length=20,
        help_text="IDs de documentos a adjuntar como contexto prioritario (opcional).",
    )

    def validate_audio(self, file):
        content_type = getattr(file, "content_type", "")
        if content_type not in _SUPPORTED_AUDIO_TYPES:
            raise serializers.ValidationError(
                f"Unsupported format '{content_type}'. Allowed: mp3, mp4, wav, webm, ogg, flac."
            )
        if file.size > _MAX_AUDIO_MB * 1024 * 1024:
            raise serializers.ValidationError(f"Audio file cannot exceed {_MAX_AUDIO_MB} MB.")
        return file

    def validate(self, attrs):
        has_text = bool(attrs.get("message"))
        has_audio = bool(attrs.get("audio"))
        has_docs = bool(attrs.get("document_ids"))
        if not has_text and not has_audio and not has_docs:
            raise serializers.ValidationError("Provide 'message' (text), 'audio' (file), or 'document_ids'.")
        if has_text and has_audio:
            raise serializers.ValidationError("Provide only one: 'message' or 'audio'.")
        return attrs


class LessonsLearnedItemResponse(serializers.ModelSerializer):
    class Meta:
        model = ArtifactLessonsLearnedItem
        fields = ["id", "category", "observation", "discussion", "recommendation", "position"]


class LessonsLearnedResponse(serializers.ModelSerializer):
    items = LessonsLearnedItemResponse(many=True)
    retrieve_context = serializers.SerializerMethodField()
    process_documents = serializers.SerializerMethodField()
    document_ids = serializers.SerializerMethodField()
    source_chat_id = serializers.SerializerMethodField()

    class Meta:
        model = ArtifactLessonsLearned
        fields = [
            "id",
            "artifact_id",
            "title",
            "query",
            "description",
            "retrieve_context",
            "process_documents",
            "document_ids",
            "items",
            "source_chat_id",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields

    def get_retrieve_context(self, obj) -> bool | None:
        return obj.artifact.retrieve_context if obj.artifact_id else None

    def get_process_documents(self, obj) -> bool | None:
        return obj.artifact.process_documents if obj.artifact_id else None

    def get_document_ids(self, obj) -> list[int]:
        return obj.artifact.document_ids if obj.artifact_id else []

    def get_source_chat_id(self, obj) -> int | None:
        return obj.artifact.source_chat_id if obj.artifact_id else None


class LessonsLearnedGenerateResponse(serializers.Serializer):
    lessons_learned = serializers.SerializerMethodField()
    messages = _MessageSerializer(many=True)
    fragments = _FragmentSerializer(many=True)

    def get_lessons_learned(self, obj):
        return LessonsLearnedResponse(obj["lessons_learned"]).data


class LessonsLearnedListResponse(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()
    retrieve_context = serializers.SerializerMethodField()
    process_documents = serializers.SerializerMethodField()
    document_ids = serializers.SerializerMethodField()
    source_chat_id = serializers.SerializerMethodField()

    class Meta:
        model = ArtifactLessonsLearned
        fields = [
            "id",
            "artifact_id",
            "title",
            "retrieve_context",
            "process_documents",
            "document_ids",
            "source_chat_id",
            "item_count",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields

    def get_item_count(self, obj: ArtifactLessonsLearned) -> int:
        return getattr(obj, "item_count", 0)

    def get_retrieve_context(self, obj) -> bool | None:
        return obj.artifact.retrieve_context if obj.artifact_id else None

    def get_process_documents(self, obj) -> bool | None:
        return obj.artifact.process_documents if obj.artifact_id else None

    def get_document_ids(self, obj) -> list[int]:
        return obj.artifact.document_ids if obj.artifact_id else []

    def get_source_chat_id(self, obj) -> int | None:
        return obj.artifact.source_chat_id if obj.artifact_id else None
