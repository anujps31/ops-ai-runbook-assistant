from app.services.retrieval_service import RetrievalService
from app.services.llm_service import LLMService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RecommendationAgent:

    def __init__(self):
        self.retriever = RetrievalService()
        self.llm = LLMService()

    def recommend(
        self,
        incident: str
    ) -> str:

        logger.info(
            "Generating recommendations..."
        )

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
You are a Senior SRE.

Incident:
{incident}

Context:
{context}

Rules:
- Use ONLY information from the context.
- Do NOT invent technologies, logs, tools, dashboards or commands.
- If information is missing, state:
  "No recommendation available from current runbooks."

Provide:

1. Immediate Actions
2. Recommended Fix
3. Preventive Actions
"""

        return self.llm.generate(prompt)