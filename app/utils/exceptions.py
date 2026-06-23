"""
Centralized exception handlers for the FastAPI application.

This module defines global exception handlers for:
  - `fastapi.HTTPException` (expected HTTP errors)
  - generic `Exception` (unexpected/unhandled errors)

Handlers return a standardized `APIResponse` envelope so that clients
always receive consistent JSON shapes regardless of error type.

Why centralized exception handling?
  - Ensures uniform error responses across all routes and modules.
  - Prevents leaking internal tracebacks or implementation details to clients.
  - Simplifies logging and monitoring by consolidating error reporting in one place.

Why logging exceptions matters:
  - Logs capture stack traces and context needed to diagnose failures.
  - Logging at appropriate levels (warning vs error) helps prioritize incidents.
  - Central logging makes it easier to integrate with aggregators (ELK, Datadog).

Difference between `HTTPException` and generic `Exception`:
  - `HTTPException` is intended for expected client-facing errors
    (e.g., 404 Not Found, 400 Bad Request) and already contains an HTTP
    status code and optional detail useful for clients.
  - Generic `Exception` represents unexpected failures in application logic
    or external services; these should be treated as 500 Internal Server Error
    and logged with full stack traces for diagnostics.

Usage:
  Call `init_exception_handlers(app)` during application setup (for example,
  in `app/main.py` after creating `app`) to register handlers with FastAPI.

Do not create route handlers in this module.
"""

from typing import Any

from fastapi import FastAPI, Request, HTTPException
from starlette.responses import JSONResponse

from app.utils.logger import get_logger
from app.models.response_models import APIResponse


# Module logger used for recording exceptions and diagnostic information
logger = get_logger(__name__)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle FastAPI `HTTPException` instances.

    This returns the exception detail to the client within the standardized
    `APIResponse` envelope and uses the exception's status code.

    We log at WARNING level because these exceptions usually indicate
    client errors or expected conditions (e.g., not found, validation failed).
    """
    # Log a concise message with request context and exception detail
    logger.warning(
        "HTTPException for %s %s — status=%s detail=%s",
        request.method,
        request.url,
        exc.status_code,
        exc.detail,
    )

    # Construct standardized response; `data` is None for errors by default
    payload = APIResponse[None](success=False, message=str(exc.detail), data=None)

    # Return JSONResponse with the original HTTP status code
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all handler for unexpected exceptions.

    Generic exceptions are logged with full stack traces to aid debugging.
    Clients receive a generic, non-sensitive message and HTTP 500 status.
    """
    # Log the full exception stack trace — critical for diagnosing bugs
    logger.exception("Unhandled exception during request %s %s", request.method, request.url)

    # Return a generic message to clients to avoid leaking internals
    payload = APIResponse[None](success=False, message="Internal Server Error", data=None)

    return JSONResponse(status_code=500, content=payload.model_dump())


def init_exception_handlers(app: FastAPI) -> None:
    """
    Register global exception handlers with the FastAPI application.

    Call this once during application initialization (for example,
    immediately after creating the `app` object in `app/main.py`).
    """
    # HTTPException handler should be registered first to preserve its status codes
    app.add_exception_handler(HTTPException, http_exception_handler)
    # Generic Exception handler acts as a final fallback
    app.add_exception_handler(Exception, generic_exception_handler)


# Example (commented) usage in `app/main.py`:
#
# from app.utils.exceptions import init_exception_handlers
#
# app = FastAPI(...)
# init_exception_handlers(app)
