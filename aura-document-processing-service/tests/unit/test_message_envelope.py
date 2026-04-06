"""Unit tests for MessageEnvelope round-trip."""

from app.infrastructure.messaging.rabbitmq.dtos.commands.document_ingestion_command import DocumentIngestionCommand
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope


def test_envelope_wrap_roundtrip_bytes() -> None:
    cmd = DocumentIngestionCommand(
        document_id=7,
        storage_url="s3://b/k",
        filename="f.pdf",
        mime_type="application/pdf",
        created_by=2,
        prefer_docling=True,
    )
    env = MessageEnvelope.wrap(cmd)
    raw = env.to_bytes()
    restored = MessageEnvelope.from_bytes(raw, DocumentIngestionCommand)
    assert restored.message_id == env.message_id
    assert restored.command.document_id == 7
    assert restored.command.prefer_docling is True
    assert restored.command.storage_url == "s3://b/k"
