from time import perf_counter

from fastapi import APIRouter, HTTPException

from app.agents.orchestrator_agent import OrchestratorAgent
from app.models.incident_models import (
    IncidentRequest,
    IncidentResponse,
    IncidentAnalysisResponse,
)
from app.models.response_models import APIResponse
from app.utils.logger import get_logger

router = APIRouter(
    prefix="/api/v1/incidents",
    tags=["Incident Analysis"]
)

logger = get_logger(__name__)
agent = OrchestratorAgent()


@router.post(
    "/analyze",
    response_model=APIResponse[IncidentResponse]
)
async def analyze_incident(
    request: IncidentRequest
):
    start_time = perf_counter()

    if not request.incident.strip():
        raise HTTPException(status_code=400, detail="Incident text cannot be empty")

    logger.info("Received incident analysis request")

    result = agent.analyze(request.incident)

    execution_time = perf_counter() - start_time

    incident_analysis = result.get("incident_analysis", {})
    if not isinstance(incident_analysis, dict):
        incident_analysis = {
            "severity": "P2",
            "summary": str(incident_analysis),
            "root_cause": "",
            "confidence_score": "0%",
            "recommended_actions": [],
            "affected_components": [],
            "business_impact": "",
            "investigation_steps": [],
        }

    return APIResponse(
        success=True,
        message="Incident analysis complete",
        data=IncidentResponse(
            incident_analysis=IncidentAnalysisResponse(**incident_analysis),
            root_cause=result.get("root_cause", ""),
            recommendations=result.get("recommendations", ""),
            execution_time_seconds=execution_time,
        ),
    )