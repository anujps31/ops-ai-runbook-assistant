from app.services.retrieval_service import RetrievalService
from app.services.llm_service import LLMService
from app.prompts.incident_prompt import INCIDENT_ANALYSIS_PROMPT
from app.utils.logger import get_logger


logger = get_logger(__name__)


class IncidentAgent:

    def __init__(self):
        self.retriever = RetrievalService()
        self.llm = LLMService()

    def analyze(
        self,
        incident: str
    ) -> str:

        logger.info(
            "Analyzing incident..."
        )

        results = self.retriever.search(
            query=incident,
            top_k=2
        )

        documents = results.get(
            "documents",
            [[]]
        )[0]

        context = "\n\n".join(documents)
        
        logger.info(
            "Retrieved Context:\n%s",
            context
        )

        prompt = INCIDENT_ANALYSIS_PROMPT.format(
            context=context,
            incident=incident
        )

        response = self.llm.generate(
            prompt=prompt
        )

        return response