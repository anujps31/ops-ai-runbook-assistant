from fastapi import APIRouter

from app.agents.orchestrator_agent import OrchestratorAgent
from app.models.incident_models import (
    IncidentRequest,
    IncidentResponse
)

router = APIRouter(
    prefix="/api/v1/incidents",
    tags=["Incident Analysis"]
)

agent = OrchestratorAgent()


@router.post(
    "/analyze",
    response_model=IncidentResponse
)
async def analyze_incident(
    request: IncidentRequest
):

    result = agent.analyze(
        request.incident
    )

    return IncidentResponse(
        incident_analysis=result["incident_analysis"],
        root_cause=result["root_cause"],
        recommendations=result["recommendations"]
    )