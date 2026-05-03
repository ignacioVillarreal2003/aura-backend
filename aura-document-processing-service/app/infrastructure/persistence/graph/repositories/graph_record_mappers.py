from datetime import datetime, timezone
from typing import Any, Optional
from neo4j.graph import Node, Relationship
from neo4j.time import DateTime as Neo4jDateTime

from app.domain.constants.graph.entity_type import EntityType
from app.domain.dtos.graph.graph_entity.graph_entity_response import GraphEntityResponse
from app.domain.dtos.graph.graph_entity.graph_relation_response import (
    GraphRelationEndpoint,
    GraphRelationResponse,
)


def _to_python_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, Neo4jDateTime):
        try:
            return value.to_native()
        except Exception:
            return None
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _coerce_int_list(value: Any) -> list[int]:
    if not value:
        return []
    out: list[int] = []
    for item in value:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out


def _coerce_str_list(value: Any) -> list[str]:
    if not value:
        return []
    out: list[str] = []
    for item in value:
        if item is None:
            continue
        out.append(str(item))
    return out


def map_entity_node(node: Any) -> GraphEntityResponse:
    if node is None:
        raise ValueError("entity node is required for mapping.")

    if isinstance(node, Node):
        properties: dict[str, Any] = dict(node)
    elif isinstance(node, dict):
        properties = node
    else:
        raise ValueError(f"unexpected entity node payload: {type(node).__name__}")

    canonical_name = str(properties.get("canonical_name") or "").strip()
    display_name = str(properties.get("display_name") or canonical_name).strip()
    raw_type = str(properties.get("type") or "")
    entity_type = EntityType.parse(raw_type)

    description = properties.get("description")
    if description is not None:
        description = str(description)

    return GraphEntityResponse(
        canonical_name=canonical_name or display_name or "unknown",
        display_name=display_name or canonical_name or "unknown",
        type=entity_type,
        aliases=_coerce_str_list(properties.get("aliases")),
        description=description,
        source_document_ids=_coerce_int_list(properties.get("source_document_ids")),
        created_at=_to_python_datetime(properties.get("created_at")),
        updated_at=_to_python_datetime(properties.get("updated_at")),
    )


def map_relationship(
        relationship: Any,
        source: GraphEntityResponse,
        target: GraphEntityResponse,
) -> GraphRelationResponse:
    if relationship is None:
        raise ValueError("relationship is required for mapping.")

    if isinstance(relationship, Relationship):
        properties: dict[str, Any] = dict(relationship)
    elif isinstance(relationship, dict):
        properties = relationship
    else:
        raise ValueError(
            f"unexpected relationship payload: {type(relationship).__name__}"
        )

    relation_type = str(properties.get("type") or "related_to")
    confidence_raw = properties.get("confidence")
    try:
        confidence = float(confidence_raw) if confidence_raw is not None else 0.5
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    return GraphRelationResponse(
        type=relation_type,
        source=GraphRelationEndpoint(
            canonical_name=source.canonical_name,
            display_name=source.display_name,
            type=source.type,
        ),
        target=GraphRelationEndpoint(
            canonical_name=target.canonical_name,
            display_name=target.display_name,
            type=target.type,
        ),
        confidence=confidence,
        source_document_ids=_coerce_int_list(properties.get("source_document_ids")),
        created_at=_to_python_datetime(properties.get("created_at")),
        updated_at=_to_python_datetime(properties.get("updated_at")),
    )
