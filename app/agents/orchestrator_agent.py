from app.agents.incident_agent import IncidentAgent
from app.agents.root_cause_agent import RootCauseAgent
from app.agents.recommendation_agent import RecommendationAgent

from app.utils.logger import get_logger

logger = get_logger(__name__)


class OrchestratorAgent:

    def __init__(self):

        self.incident_agent = IncidentAgent()
        self.root_cause_agent = RootCauseAgent()
        self.recommendation_agent = RecommendationAgent()

    def analyze(self, incident: str):

        logger.info("Running orchestrator")

        incident_analysis = self.incident_agent.analyze(
            incident
        )

        root_cause = self.root_cause_agent.analyze(
            incident
        )

        recommendations = self.recommendation_agent.recommend(
            incident
        )

        return {
            "incident_analysis": incident_analysis,
            "root_cause": root_cause,
            "recommendations": recommendations
        }