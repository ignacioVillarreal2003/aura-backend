from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.artifact.models import Artifact, ArtifactVersion
from apps.artifact.models.artifact_pin import ArtifactPin


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


class UpdateArtifactRequest(serializers.Serializer):
    title = serializers.CharField(max_length=500, allow_blank=False, required=False)
    description = serializers.CharField(allow_blank=True, required=False)
    status = serializers.ChoiceField(choices=Artifact.Status.choices, required=False)
    change_summary = serializers.CharField(allow_blank=True, required=False, default="")

    def validate(self, data):
        if not any(k in data for k in ("title", "description", "status")):
            raise serializers.ValidationError("Se requiere al menos un campo a actualizar.")
        return data


class ArtifactMessagePreview(serializers.Serializer):
    id = serializers.IntegerField()
    message = serializers.CharField()
    sender_type = serializers.CharField()
    created_at = serializers.DateTimeField()


class ArtifactSummaryResponse(serializers.ModelSerializer):
    message = serializers.SerializerMethodField()
    linked_id = serializers.SerializerMethodField()
    is_bookmarked = serializers.SerializerMethodField()
    user_feedback = serializers.SerializerMethodField()
    thread_reply_count = serializers.SerializerMethodField()

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
            "is_bookmarked",
            "user_feedback",
            "thread_reply_count",
            "source_chat_id",
            "created_by",
            "created_at",
            "updated_at",
            "message",
            "linked_id",
        ]
        read_only_fields = fields

    @extend_schema_field(ArtifactMessagePreview(allow_null=True))
    def get_message(self, obj):
        if obj.type != Artifact.Type.MESSAGE:
            return None
        try:
            mc = obj.message_content
        except ObjectDoesNotExist:
            return None
        return ArtifactMessagePreview(mc).data

    @extend_schema_field(serializers.BooleanField())
    def get_is_bookmarked(self, obj):
        from apps.artifact.models.artifact_bookmark import ArtifactBookmark
        request = self.context.get('request')
        if not request:
            return False
        return ArtifactBookmark.objects.filter(artifact_id=obj.id, created_by=request.user.id).exists()

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_user_feedback(self, obj):
        from apps.artifact.models.artifact_feedback import ArtifactFeedback
        request = self.context.get('request')
        if not request:
            return None
        fb = ArtifactFeedback.objects.filter(artifact_id=obj.id, user_id=request.user.id).first()
        return fb.value if fb else None

    @extend_schema_field(serializers.IntegerField())
    def get_thread_reply_count(self, obj):
        from apps.artifact.models.artifact_thread_reply import ArtifactThreadReply
        return ArtifactThreadReply.objects.filter(parent_artifact_id=obj.id).count()

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_linked_id(self, obj):
        try:
            if obj.type == Artifact.Type.REPORT:
                return obj.report_content.id
            if obj.type == Artifact.Type.CHECKLIST:
                return obj.checklist_content.id
            if obj.type == Artifact.Type.QUIZ:
                return obj.quiz_content.id
            if obj.type == Artifact.Type.TIMELINE:
                return obj.timeline_content.id
            if obj.type == Artifact.Type.LESSONS_LEARNED:
                return obj.lessons_learned_content.id
            if obj.type == Artifact.Type.DECISION_BRIEF:
                return obj.decision_brief_content.id
            if obj.type == Artifact.Type.DOCUMENT_SUMMARY:
                return obj.document_summary_content.id
            if obj.type == Artifact.Type.DOCUMENT_ACTION:
                return obj.document_action_content.id
        except ObjectDoesNotExist:
            return None
        return None


class PinnedArtifactResponse(serializers.ModelSerializer):
    artifact = ArtifactSummaryResponse(read_only=True)

    class Meta:
        model = ArtifactPin
        fields = ["id", "artifact_id", "chat_id", "created_by", "created_at", "artifact"]
        read_only_fields = fields
