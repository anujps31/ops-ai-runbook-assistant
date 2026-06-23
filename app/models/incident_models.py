from pydantic import BaseModel


class IncidentRequest(BaseModel):
    incident: str


class IncidentResponse(BaseModel):
    incident_analysis: str
    root_cause: str
    recommendations: str