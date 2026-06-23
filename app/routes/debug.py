"""
Debug routes

This module provides endpoints useful during development to validate
application behavior such as exception handling, logging, and monitoring.

WARNING: Endpoints in this module are intended for testing only and should
be disabled or removed in production environments.
"""

from fastapi import APIRouter

from app.utils.logger import get_logger


# Router for debug endpoints. Prefix keeps routes grouped under /debug.
router = APIRouter(prefix="/debug", tags=["debug"])


# Module-level logger for debug routes
logger = get_logger(__name__)


@router.get("/error")
async def trigger_error():
    """
    Intentionally raise an exception to test global exception handling.

    Operational notes:
      - Calls to this endpoint will log a message and then raise an exception.
      - Use this to verify that `app/utils/exceptions.py` handlers are
        registered and return standardized error responses.
      - Do NOT enable this in production or expose it publicly.
    """
    # Log an informational message before raising so the logs include the
    # intent to trigger an error; this helps confirm both logging and
    # exception handling pipelines are exercised.
    logger.info("/debug/error endpoint invoked — raising test exception")

    # Raise a test exception that should be handled by the global handler
    raise Exception("Test exception")
