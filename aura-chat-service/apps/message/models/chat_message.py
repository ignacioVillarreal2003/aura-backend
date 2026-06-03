from apps.artifact.models.artifact_message import ArtifactMessage

# Backward-compatible alias so existing imports keep working while the codebase
# is migrated. Prefer importing ArtifactMessage directly.
ChatMessage = ArtifactMessage
