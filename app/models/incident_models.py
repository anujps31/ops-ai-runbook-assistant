from typing import List

from pydantic import BaseModel


class IncidentRequest(BaseModel):
    incident: str


class IncidentAnalysisResponse(BaseModel):
    severity: str
    summary: str
    root_cause: str
    confidence_score: str
    recommended_actions: List[str]
    affected_components: List[str]
    business_impact: str
    investigation_steps: List[str]


class IncidentResponse(BaseModel):
    incident_analysis: IncidentAnalysisResponse
    root_cause: str
    recommendations: str
    execution_time_seconds: float