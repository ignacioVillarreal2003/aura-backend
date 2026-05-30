from rest_framework import serializers

from apps.checklist.models import Checklist


class _MessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["human", "assistant"])
    content = serializers.CharField()


class _FragmentSerializer(serializers.Serializer):
    document = serializers.DictField(required=False)
    content = serializers.CharField(required=False, default="")


class GenerateChecklistRequest(serializers.Serializer):
    mode = serializers.ChoiceField(choices=Checklist.Mode.choices)
    message = serializers.CharField(allow_blank=False, max_length=4000)
    chat_id = serializers.IntegerField(required=False, allow_null=True)


class ChecklistGenerateResponse(serializers.Serializer):
    checklist = serializers.SerializerMethodField()
    messages = _MessageSerializer(many=True)
    fragments = _FragmentSerializer(many=True)

    def get_checklist(self, obj):
        return ChecklistResponse(obj["checklist"]).data


class ChecklistItemSerializer(serializers.Serializer):
    id = serializers.CharField()
    section = serializers.CharField(max_length=200)
    order = serializers.IntegerField(min_value=1)
    text = serializers.CharField(max_length=500)
    is_checked = serializers.BooleanField(default=False)
    notes = serializers.CharField(default="", allow_blank=True)


class UpdateChecklistRequest(serializers.Serializer):
    title = serializers.CharField(max_length=500, allow_blank=False, required=False)
    items = ChecklistItemSerializer(many=True, required=False)

    def validate(self, data):
        if not data:
            raise serializers.ValidationError("Se requiere al menos un campo a actualizar.")
        return data

    def validate_items(self, value):
        if value is not None and len(value) > 200:
            raise serializers.ValidationError("La checklist no puede superar los 200 ítems.")
        return value


class ChecklistResponse(serializers.ModelSerializer):
    class Meta:
        model = Checklist
        fields = [
            "id",
            "title",
            "items",
            "mode",
            "metadata",
            "source_chat_id",
            "created_by",
            "created_at",
            "updated_by",
            "updated_at",
        ]
        read_only_fields = fields


class ChecklistListResponse(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()
    checked_count = serializers.SerializerMethodField()

    class Meta:
        model = Checklist
        fields = [
            "id",
            "title",
            "mode",
            "source_chat_id",
            "item_count",
            "checked_count",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields

    def get_item_count(self, obj: Checklist) -> int:
        return len(obj.items) if isinstance(obj.items, list) else 0

    def get_checked_count(self, obj: Checklist) -> int:
        if not isinstance(obj.items, list):
            return 0
        return sum(1 for item in obj.items if isinstance(item, dict) and item.get("is_checked"))
