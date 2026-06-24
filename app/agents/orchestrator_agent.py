from concurrent.futures import ThreadPoolExecutor, as_completed

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
        logger.info("Starting parallel orchestration of incident agents")

        results = {
            "incident_analysis": None,
            "root_cause": None,
            "recommendations": None,
        }

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self.incident_agent.analyze, incident): "incident_analysis",
                executor.submit(self.root_cause_agent.analyze, incident): "root_cause",
                executor.submit(self.recommendation_agent.recommend, incident): "recommendations",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    results[key] = future.result()
                    logger.info("Agent %s completed successfully", key)
                except Exception as exc:
                    logger.error("Agent %s failed: %s", key, exc)
                    results[key] = ""

        return results