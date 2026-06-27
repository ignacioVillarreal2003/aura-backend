from rest_framework import serializers

from apps.artifact.shared_serializers import FragmentSerializer as _FragmentSerializer, \
    MessageSerializer as _MessageSerializer
from apps.artifact_quiz.models import ArtifactQuiz, ArtifactQuizOption, ArtifactQuizQuestion
from core.validators.audio import MAX_AUDIO_MB as _MAX_AUDIO_MB, SUPPORTED_AUDIO_TYPES as _SUPPORTED_AUDIO_TYPES


class GenerateQuizRequest(serializers.Serializer):
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


class QuizOptionResponse(serializers.ModelSerializer):
    class Meta:
        model = ArtifactQuizOption
        fields = ["id", "text", "position"]


class QuizQuestionResponse(serializers.ModelSerializer):
    options = QuizOptionResponse(many=True)
    correct_option_ids = serializers.SerializerMethodField()

    class Meta:
        model = ArtifactQuizQuestion
        fields = ["id", "text", "kind", "explanation", "position", "options",
                  "selected_option_id", "correct_option_ids"]

    def get_correct_option_ids(self, obj) -> list[int]:
        # Solo se revelan las opciones correctas si la pregunta ya fue respondida.
        if obj.selected_option_id is None:
            return []
        return [opt.id for opt in obj.options.all() if opt.is_correct]


class QuizAnswerRequest(serializers.Serializer):
    option_id = serializers.IntegerField()


class QuizAnswerResponse(serializers.Serializer):
    question_id = serializers.IntegerField()
    selected_option_id = serializers.IntegerField()
    is_correct = serializers.BooleanField()
    correct_option_ids = serializers.ListField(child=serializers.IntegerField())
    answered_count = serializers.IntegerField()
    correct_count = serializers.IntegerField()
    total_questions = serializers.IntegerField()
    score_pct = serializers.IntegerField()


class QuizResponse(serializers.ModelSerializer):
    questions = QuizQuestionResponse(many=True)
    retrieve_context = serializers.SerializerMethodField()
    process_documents = serializers.SerializerMethodField()
    document_ids = serializers.SerializerMethodField()
    source_chat_id = serializers.SerializerMethodField()
    total_questions = serializers.SerializerMethodField()
    answered_count = serializers.SerializerMethodField()
    correct_count = serializers.SerializerMethodField()
    score_pct = serializers.SerializerMethodField()

    class Meta:
        model = ArtifactQuiz
        fields = [
            "id",
            "artifact_id",
            "title",
            "query",
            "instructions",
            "retrieve_context",
            "process_documents",
            "document_ids",
            "questions",
            "total_questions",
            "answered_count",
            "correct_count",
            "score_pct",
            "source_chat_id",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields

    @staticmethod
    def _progress(obj) -> tuple[int, int, int]:
        questions = list(obj.questions.all())
        total = len(questions)
        answered = 0
        correct = 0
        for q in questions:
            if q.selected_option_id is None:
                continue
            answered += 1
            if any(o.id == q.selected_option_id and o.is_correct for o in q.options.all()):
                correct += 1
        return total, answered, correct

    def get_total_questions(self, obj) -> int:
        return self._progress(obj)[0]

    def get_answered_count(self, obj) -> int:
        return self._progress(obj)[1]

    def get_correct_count(self, obj) -> int:
        return self._progress(obj)[2]

    def get_score_pct(self, obj) -> int:
        total, _answered, correct = self._progress(obj)
        return round(correct / total * 100) if total else 0

    def get_retrieve_context(self, obj) -> bool | None:
        return obj.artifact.retrieve_context if obj.artifact_id else None

    def get_process_documents(self, obj) -> bool | None:
        return obj.artifact.process_documents if obj.artifact_id else None

    def get_document_ids(self, obj) -> list[int]:
        return obj.artifact.document_ids if obj.artifact_id else []

    def get_source_chat_id(self, obj) -> int | None:
        return obj.artifact.source_chat_id if obj.artifact_id else None


class QuizGenerateResponse(serializers.Serializer):
    quiz = serializers.SerializerMethodField()
    messages = _MessageSerializer(many=True)
    fragments = _FragmentSerializer(many=True)

    def get_quiz(self, obj):
        return QuizResponse(obj["quiz"]).data


class QuizListResponse(serializers.ModelSerializer):
    question_count = serializers.SerializerMethodField()
    retrieve_context = serializers.SerializerMethodField()
    process_documents = serializers.SerializerMethodField()
    document_ids = serializers.SerializerMethodField()
    source_chat_id = serializers.SerializerMethodField()

    class Meta:
        model = ArtifactQuiz
        fields = [
            "id",
            "artifact_id",
            "title",
            "retrieve_context",
            "process_documents",
            "document_ids",
            "source_chat_id",
            "question_count",
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

    def get_question_count(self, obj: ArtifactQuiz) -> int:
        return getattr(obj, "question_count", 0)
