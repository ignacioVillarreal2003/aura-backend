import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass
class MessageEnvelope(Generic[T]):
    message_id: str
    command: T
    published_at: datetime
    version: int = 1
    retry_count: int = 0

    @classmethod
    def wrap(
            cls,
            command: T,
    ) -> "MessageEnvelope[T]":
        return cls(
            message_id=str(uuid.uuid4()),
            command=command,
            published_at=datetime.now(timezone.utc)
        )

    def to_bytes(
            self
    ) -> bytes:
        payload = {
            "message_id": self.message_id,
            "published_at": self.published_at.isoformat(),
            "version": self.version,
            "command": self.command.model_dump()
        }
        return json.dumps(payload).encode("utf-8")

    @classmethod
    def from_bytes(
            cls,
            data: bytes,
            command_type: type[T],
            retry_count: int = 0,
    ) -> "MessageEnvelope[T]":
        payload = json.loads(data.decode("utf-8"))
        return cls(
            message_id=payload["message_id"],
            command=command_type.model_validate(payload["command"]),
            published_at=datetime.fromisoformat(payload["published_at"]),
            version=payload.get("version", 1),
            retry_count=retry_count,
        )
