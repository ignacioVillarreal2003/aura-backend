from fastapi import Request


def get_document_catalog_authorization_header(
        request: Request,
) -> str | None:
    """Prefer the caller Bearer token from middleware; optionally fall back to a service token."""
    header = getattr(request.state, "authorization_header_outbound", None)
    if isinstance(header, str) and header.strip():
        return header.strip()

    fallback = getattr(request.app.state, "document_collection_catalog_fallback_bearer", None)
    if isinstance(fallback, str) and fallback.strip():
        stripped = fallback.strip()
        return stripped if stripped.lower().startswith("bearer ") else f"Bearer {stripped}"

    return None
