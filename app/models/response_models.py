"""
Reusable API response models

This module defines a standard, generic response envelope used across the
application. Wrapping API responses in a consistent structure makes client
integration, error handling, and logging simpler and more predictable.

The `APIResponse` model is generic so that `data` can be any type (including
another Pydantic model, list, dict, or primitive). Use it as the `response_model`
on FastAPI routes to enforce consistent response shapes and generate
accurate OpenAPI documentation.

Example usage (in a route, not included here):

    from app.models.response_models import APIResponse
    from app.models.incident import IncidentResponse

    @app.get("/incidents/{id}", response_model=APIResponse[IncidentResponse])
    async def get_incident(id: str):
        incident = ...  # fetch or compute IncidentResponse
        return APIResponse(success=True, message="OK", data=incident)

"""

from typing import Generic, Optional, TypeVar

from pydantic import Field
from pydantic.generics import GenericModel

# Generic type variable for the response payload
T = TypeVar("T")


class APIResponse(GenericModel, Generic[T]):
    """
    Standard API response envelope

    Fields:
        - success: bool
            Indicates whether the request completed successfully from the
            application's point of view. This is distinct from HTTP status
            codes and is useful for clients that rely on an explicit success
            flag.

        - message: str
            Human-readable message intended for operators and clients. Use
            short strings like "OK", "Not Found", or descriptive error
            messages when appropriate.

        - data: Optional[T]
            Optional payload. When present, its type is generic and typically
            a Pydantic model, dict, list, or primitive value. Absent (None)
            for operations that don't return data.

    Notes:
        - Use this model as `response_model` in FastAPI route decorators to
          ensure OpenAPI schemas include the envelope and the inner data
          type (e.g., `APIResponse[MyModel]`).
        - Keep the envelope small and predictable to make client parsing
          and monitoring simpler.
    """

    success: bool = Field(..., description="True when request succeeded")
    message: str = Field(..., description="Human-readable summary of the result")
    data: Optional[T] = Field(None, description="Optional payload for the response")


class EmptyResponse(APIResponse[None]):
    """
    Convenience alias for responses that do not include a payload.

    Example:
        return EmptyResponse(success=True, message="Deleted")
    """

    data: Optional[None] = None
