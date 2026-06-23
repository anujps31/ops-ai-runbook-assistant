"""
Reusable response helpers

Provides two simple helper functions that create standardized API response
envelopes using the `APIResponse` model. These helpers centralize the
formatting of success and error responses to ensure consistency across the
application and simplify route code.

Functions:
    - success_response(data=None, message="OK") -> APIResponse[T]
    - error_response(message, data=None) -> APIResponse[Optional[T]]

Usage:
    from app.utils.response import success_response, error_response
    from app.models.response_models import APIResponse, EmptyResponse

    @app.get("/example", response_model=APIResponse[MyModel])
    async def example():
        payload = MyModel(...)
        return success_response(payload)

"""

from typing import Generic, Optional, TypeVar

from app.models.response_models import APIResponse

# Generic type variable for payload
T = TypeVar("T")


def success_response(data: Optional[T] = None, message: str = "OK") -> APIResponse[Optional[T]]:
    """
    Build a standardized success response.

    Args:
        data (Optional[T]): Optional payload to include in the response.
        message (str): Human-readable message. Defaults to "OK".

    Returns:
        APIResponse[Optional[T]]: Standard API response with `success=True`.

    Operational notes:
        - Use this helper in route handlers to return successful results.
        - Keeps controllers thin by moving envelope construction into one place.
    """
    return APIResponse(success=True, message=message, data=data)


def error_response(message: str, data: Optional[T] = None) -> APIResponse[Optional[T]]:
    """
    Build a standardized error response.

    Args:
        message (str): Human-readable error message describing the failure.
        data (Optional[T]): Optional additional payload (e.g., error details).

    Returns:
        APIResponse[Optional[T]]: Standard API response with `success=False`.

    Operational notes:
        - Keep error messages concise and non-sensitive; avoid exposing
          internal details in production environments.
        - Use `data` for structured error metadata when needed (validation
          details, error codes) but prefer lightweight responses for public
          APIs.
    """
    return APIResponse(success=False, message=message, data=data)
