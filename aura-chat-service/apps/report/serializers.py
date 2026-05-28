from rest_framework import serializers

from apps.report.models import Report


class _MessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["human", "assistant"])
    content = serializers.CharField()


class _FragmentSerializer(serializers.Serializer):
    document = serializers.DictField(required=False)
    content = serializers.CharField(required=False, default="")


class GenerateReportRequest(serializers.Serializer):
    type = serializers.ChoiceField(choices=Report.Type.choices)
    mode = serializers.ChoiceField(choices=Report.Mode.choices)
    message = serializers.CharField(allow_blank=False)


class ReportGenerateResponse(serializers.Serializer):
    report = serializers.SerializerMethodField()
    messages = _MessageSerializer(many=True)
    fragments = _FragmentSerializer(many=True)

    def get_report(self, obj):
        from apps.report.serializers import ReportResponse
        return ReportResponse(obj["report"]).data


class UpdateReportRequest(serializers.Serializer):
    title = serializers.CharField(max_length=500, allow_blank=False, required=False)
    content = serializers.CharField(allow_blank=False, required=False)

    def validate(self, data):
        if not data:
            raise serializers.ValidationError("Se requiere al menos un campo a actualizar.")
        return data


class ReportResponse(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = [
            "id",
            "type",
            "title",
            "content",
            "mode",
            "metadata",
            "created_by",
            "created_at",
            "updated_by",
            "updated_at",
        ]
        read_only_fields = fields


class ReportListResponse(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = [
            "id",
            "type",
            "title",
            "mode",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields
