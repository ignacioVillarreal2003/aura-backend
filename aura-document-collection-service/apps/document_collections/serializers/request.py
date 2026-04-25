from rest_framework import serializers


def _normalize_document_collection_name(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise serializers.ValidationError("Name must not be empty or whitespace only.")
    if len(cleaned) > 255:
        raise serializers.ValidationError("Name must be at most 255 characters after trimming.")
    return cleaned


class CreateDocumentCollectionRequest(serializers.Serializer):
    name = serializers.CharField(max_length=255, trim_whitespace=True)

    def validate_name(self, value: str) -> str:
        return _normalize_document_collection_name(value)


class PatchDocumentCollectionRequest(serializers.Serializer):
    name = serializers.CharField(max_length=255, trim_whitespace=True)

    def validate_name(self, value: str) -> str:
        return _normalize_document_collection_name(value)
