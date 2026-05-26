from rest_framework import serializers

from apps.report.models import Report


class CreateReportRequest(serializers.Serializer):
    type = serializers.ChoiceField(choices=Report.Type.choices)
    title = serializers.CharField(max_length=500, allow_blank=False)
    content = serializers.CharField(allow_blank=False)
    mode = serializers.ChoiceField(choices=Report.Mode.choices)
    metadata = serializers.DictField(default=dict)


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
