# Health check route module
# This module provides endpoints for monitoring application availability

from fastapi import APIRouter
from app.utils.logger import get_logger


# Module-level logger for health routes
# Logging in route modules provides operational visibility into endpoint usage
logger = get_logger(__name__)

# Create a router instance that groups related endpoints
# APIRouter allows us to organize routes modularly and register them with the main app
router = APIRouter(
    prefix="/health",  # All routes in this router will start with /health
    tags=["health"],   # Tags organize endpoints in OpenAPI documentation
)


@router.get("")
async def get_health():
    """
    Health check endpoint
    
    Returns:
        dict: Status information for monitoring and health checks
    
    Example response:
        {
            "status": "healthy",
            "service": "ops-ai-runbook-assistant"
        }
    """
    # Log that the health endpoint was invoked. This helps operators and
    # on-call engineers understand traffic patterns and verify liveness probes.
    logger.info("/health endpoint called")

    # Prepare the response payload (kept identical to previous behavior)
    response = {
        "status": "healthy",
        "service": "ops-ai-runbook-assistant",
    }

    # Log the returned status for auditing and quick diagnostics. Recording
    # the exact payload returned by health checks can help detect
    # misconfigurations or drift between environments.
    logger.info("/health response: %s", response)

    return response
