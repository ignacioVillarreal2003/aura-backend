from apps.artifact.models import Artifact, ArtifactVersion


class ArtifactVersionRepository:
    def add_version(self, *, artifact: Artifact, created_by: int, change_summary: str = "") -> ArtifactVersion:
        return ArtifactVersion.objects.create(
            artifact=artifact,
            version_number=artifact.version,
            title=artifact.title,
            description=artifact.description,
            status=artifact.status,
            mode=artifact.mode,
            change_summary=change_summary,
            created_by=created_by,
        )

    def list_for_artifact(self, artifact_id: int):
        return ArtifactVersion.objects.filter(artifact_id=artifact_id)


artifact_version_repository = ArtifactVersionRepository()
