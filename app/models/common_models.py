"""
Common reusable Pydantic models for request envelopes and metadata.

This module provides small, generic building blocks to construct API
request contracts across the application. Keeping these models centralized
improves consistency, validation, and maintainability.

Design principles:
  - Keep models small and composable so endpoints can mix-and-match pieces.
  - Use Pydantic validation to enforce API contracts at the boundary.
  - Prefer explicit fields and types so OpenAPI schemas are clear to clients.

Examples:
  - `RequestMetadata` captures tracing and client information common to many requests
  - `BaseRequest[T]` is a generic envelope that wraps a payload with metadata

Validation, API contracts, and maintainability notes:
  - Validation: Pydantic runs type coercion and validation automatically when
    models are instantiated. This prevents invalid data from propagating into
    business logic and provides immediate, standardized errors to clients.
  - API contracts: Using typed models as route parameters (`body: BaseRequest[MyModel]`)
    creates explicit contracts that are included in OpenAPI docs, aiding client
    generation and integration tests.
  - Maintainability: Centralizing common models reduces duplication. When a
    metadata field needs to change (e.g., add `request_id`), update it once here
    and all routes benefit automatically.

Do NOT add endpoint-specific fields here; keep models generic and reusable.
"""

from typing import Any, Dict, Generic, Optional, TypeVar

from pydantic import BaseModel, Field, constr, conint
from pydantic.generics import GenericModel

# Generic type for payloads carried inside request envelopes
T = TypeVar("T")


class RequestMetadata(BaseModel):
    """
    Standard metadata attached to incoming API requests.

    Fields:
        - request_id: Optional[str] — Correlation id for distributed tracing
        - client_id: Optional[str] — Identifier for the calling client/service
        - user_id: Optional[str] — Authenticated user id when available
        - locale: Optional[str] — Locale string for localization (e.g., en-US)
        - timeout_ms: Optional[int] — Client-requested timeout in milliseconds

    Rationale:
        - Including metadata in a single model makes it easy to validate and
          pass context to service layers and agents.
        - Use `request_id` to link logs, traces, and monitoring metrics.
    """

    request_id: Optional[constr(strip_whitespace=True, min_length=1)] = Field(
        None, description="Optional correlation id for tracing across services"
    )
    client_id: Optional[constr(strip_whitespace=True, min_length=1)] = Field(
        None, description="Identifier for the calling client or service"
    )
    user_id: Optional[constr(strip_whitespace=True, min_length=1)] = Field(
        None, description="Authenticated user id if available"
    )
    locale: Optional[constr(strip_whitespace=True, min_length=2, max_length=10)] = Field(
        None, description="Locale for user-facing messages (e.g., en-US)"
    )
    timeout_ms: Optional[conint(ge=0)] = Field(
        None, description="Optional client-requested timeout in milliseconds"
    )


class BaseRequest(GenericModel, Generic[T]):
    """
    Generic request envelope used by most API endpoints.

    Structure:
        {
            "metadata": { ... },  # RequestMetadata
            "payload": { ... }    # T (arbitrary Pydantic model or primitive)
        }

    Usage:
        class MyPayload(BaseModel):
            name: str

        @app.post("/items", response_model=APIResponse[Item])
        async def create_item(req: BaseRequest[MyPayload]):
            payload = req.payload
            metadata = req.metadata
            # Process request

    Notes on validation and contracts:
        - Pydantic will validate both `metadata` and `payload` according to their
          type annotations. If `T` is a Pydantic model, its fields will be validated.
        - Use `response_model` on routes to reflect the expected response structure
          in OpenAPI documentation.
        - Keep this envelope generic so it can be reused across many endpoints.
    """

    metadata: Optional[RequestMetadata] = Field(
        None,
        description="Optional metadata providing request context (tracing, client info)",
    )
    payload: Optional[T] = Field(None, description="Payload for the request")


class PaginationParams(BaseModel):
    """
    Common pagination parameters used by list endpoints.

    Fields:
        - limit: number of items per page (bounded to prevent abusive requests)
        - offset: zero-based offset into a result set
    """

    limit: int = Field(50, ge=1, le=1000, description="Number of items to return")
    offset: int = Field(0, ge=0, description="Zero-based offset into the result set")


class CursorParams(BaseModel):
    """
    Alternative cursor-based pagination parameters.

    Cursor pagination is preferable for large datasets or real-time feeds where
    offset-based pagination is inefficient or inconsistent.
    """

    cursor: Optional[str] = Field(None, description="Opaque cursor token")
    limit: int = Field(50, ge=1, le=1000, description="Maximum number of items")


# Mark todo complete in module-level comment (for maintainers):
# - Add endpoint-specific envelopes in their own modules when necessary.
