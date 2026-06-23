from app.services.retrieval_service import RetrievalService
from app.services.llm_service import LLMService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RootCauseAgent:

    def __init__(self):
        self.retriever = RetrievalService()
        self.llm = LLMService()

    def analyze(self, incident: str) -> str:

        logger.info("Running root cause analysis...")

        results = self.retriever.search(
            query=incident,
            top_k=3
        )

        documents = results.get(
            "documents",
            [[]]
        )[0]

        context = "\n\n".join(documents)

        prompt = f"""
You are a Senior SRE and DevOps engineer.

Incident:
{incident}

Context:
{context}

Perform root cause analysis.

Provide:

1. Most likely root cause
2. Evidence
3. Confidence level
4. Recommended verification steps
"""

        response = self.llm.generate(
            prompt=prompt
        )

        return response