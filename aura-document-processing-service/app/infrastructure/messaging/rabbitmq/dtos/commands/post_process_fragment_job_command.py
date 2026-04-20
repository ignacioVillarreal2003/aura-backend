from pydantic import BaseModel, Field


class PostProcessFragmentJobCommand(BaseModel):
    """Minimal AMQP payload; full job parameters live in Redis (manifest)."""

    job_id: str = Field(..., min_length=16, max_length=64)
