"""
Health response models

This module defines the Pydantic models used for service health responses.
Keeping a dedicated model ensures the health endpoint has a stable, documented
contract that can be referenced by monitoring systems, load balancers, and
automated checks.

Design notes:
  - Health responses should be compact and predictable to minimize overhead
    in readiness/liveness probes.
  - Include `version` so operators can quickly verify the deployed artifact.
  - Use Pydantic `BaseModel` to leverage validation, documentation, and
    serialization benefits.

Example usage (route not included here):

    @app.get("/health", response_model=HealthResponse)
    async def health():
        return HealthResponse(status="healthy", service=settings.APP_NAME, version=settings.APP_VERSION)

"""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """
    Response model for health endpoints.

    Fields:
        - status: str — Short status string (e.g., "healthy", "unhealthy")
        - service: str — Logical service name for identification in multi-service setups
        - version: str — Application version (semantic versioning recommended)

    Validation and API contract:
        - Using `BaseModel` ensures values are validated and serialized to JSON
          consistently (e.g., `version` will always be a string).
        - Declaring this model as `response_model` on the route produces an
          accurate OpenAPI schema for clients and monitoring tools.

    Maintainability:
        - Keep this model small and stable; breaking changes here will impact
          health checks and tooling that depend on the shape of the response.
        - If additional metadata is required in the future (e.g., `uptime`),
          add fields carefully and consider backward compatibility for probes.
    """

    status: str = Field(..., description="Health status (e.g., 'healthy' or 'unhealthy')")
    service: str = Field(..., description="Logical service name")
    version: str = Field(..., description="Application version string")
