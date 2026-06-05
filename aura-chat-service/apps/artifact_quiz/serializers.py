from django.conf import settings
from rest_framework import serializers

from apps.artifact.models.artifact import Artifact
from apps.artifact.shared_serializers import FragmentSerializer as _FragmentSerializer, MessageSerializer as _MessageSerializer
from apps.artifact_quiz.models import ArtifactQuiz, ArtifactQuizOption, ArtifactQuizQuestion

_SUPPORTED_AUDIO_TYPES = {
    "audio/mpeg", "audio/mp4", "audio/wav", "audio/webm",
    "audio/ogg", "audio/flac", "audio/x-wav", "audio/x-m4a",
}
_MAX_AUDIO_MB = int(getattr(settings, "AUDIO_MAX_UPLOAD_MB", 25))


class GenerateQuizRequest(serializers.Serializer):
    mode = serializers.ChoiceField(choices=Artifact.Mode.choices)
    message = serializers.CharField(allow_blank=False, max_length=4000, required=False)
    audio = serializers.FileField(required=False)
    chat_id = serializers.IntegerField()

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
        if not has_text and not has_audio:
            raise serializers.ValidationError("Provide either 'message' (text) or 'audio' (file).")
        if has_text and has_audio:
            raise serializers.ValidationError("Provide only one: 'message' or 'audio'.")
        return attrs


class QuizOptionResponse(serializers.ModelSerializer):
    class Meta:
        model = ArtifactQuizOption
        fields = ["id", "text", "is_correct", "position"]


class QuizQuestionResponse(serializers.ModelSerializer):
    options = QuizOptionResponse(many=True)

    class Meta:
        model = ArtifactQuizQuestion
        fields = ["id", "text", "kind", "explanation", "position", "options"]


class QuizResponse(serializers.ModelSerializer):
    questions = QuizQuestionResponse(many=True)
    title = serializers.SerializerMethodField()
    mode = serializers.SerializerMethodField()
    source_chat_id = serializers.SerializerMethodField()

    class Meta:
        model = ArtifactQuiz
        fields = [
            "id",
            "artifact_id",
            "title",
            "instructions",
            "pass_score",
            "mode",
            "questions",
            "source_chat_id",
            "created_by",
            "created_at",
            "updated_by",
            "updated_at",
        ]
        read_only_fields = fields

    def get_title(self, obj) -> str:
        return obj.artifact.title if obj.artifact_id else ""

    def get_mode(self, obj) -> str:
        return obj.artifact.mode if obj.artifact_id else ""

    def get_source_chat_id(self, obj) -> int | None:
        return obj.artifact.source_chat_id if obj.artifact_id else None


class QuizGenerateResponse(serializers.Serializer):
    quiz = serializers.SerializerMethodField()
    messages = _MessageSerializer(many=True)
    fragments = _FragmentSerializer(many=True)

    def get_quiz(self, obj):
        return QuizResponse(obj["quiz"]).data


class _UpdateOptionRequest(serializers.Serializer):
    text = serializers.CharField(max_length=500)
    is_correct = serializers.BooleanField(default=False)
    position = serializers.IntegerField(min_value=0)


class _UpdateQuestionRequest(serializers.Serializer):
    text = serializers.CharField()
    kind = serializers.ChoiceField(choices=ArtifactQuizQuestion.Kind.choices)
    explanation = serializers.CharField(default="", allow_blank=True)
    position = serializers.IntegerField(min_value=0)
    options = _UpdateOptionRequest(many=True, required=False, default=list)


class UpdateQuizRequest(serializers.Serializer):
    title = serializers.CharField(max_length=500, allow_blank=False, required=False)
    instructions = serializers.CharField(allow_blank=True, required=False)
    pass_score = serializers.IntegerField(min_value=0, max_value=100, required=False, allow_null=True)
    questions = _UpdateQuestionRequest(many=True, required=False)

    def validate(self, data):
        if not data:
            raise serializers.ValidationError("Se requiere al menos un campo a actualizar.")
        return data

    def validate_questions(self, value):
        if len(value) > 200:
            raise serializers.ValidationError("El cuestionario no puede superar las 200 preguntas.")
        return value


class QuizListResponse(serializers.ModelSerializer):
    question_count = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    mode = serializers.SerializerMethodField()
    source_chat_id = serializers.SerializerMethodField()

    class Meta:
        model = ArtifactQuiz
        fields = [
            "id",
            "artifact_id",
            "title",
            "mode",
            "pass_score",
            "source_chat_id",
            "question_count",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields

    def get_title(self, obj) -> str:
        return obj.artifact.title if obj.artifact_id else ""

    def get_mode(self, obj) -> str:
        return obj.artifact.mode if obj.artifact_id else ""

    def get_source_chat_id(self, obj) -> int | None:
        return obj.artifact.source_chat_id if obj.artifact_id else None

    def get_question_count(self, obj: ArtifactQuiz) -> int:
        return getattr(obj, "question_count", 0)
