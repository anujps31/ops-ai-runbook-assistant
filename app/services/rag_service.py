from app.services.retrieval_service import RetrievalService
from app.services.llm_service import LLMService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RAGService:

    def __init__(self):
        self.retriever = RetrievalService()
        self.llm = LLMService()

    def ask(
        self,
        question: str,
        top_k: int = 3
    ) -> str:

        logger.info(
            "Running RAG query: %s",
            question
        )

        retrieval_results = self.retriever.search(
            query=question,
            top_k=top_k
        )

        documents = retrieval_results.get(
            "documents",
            [[]]
        )[0]

        context = "\n\n".join(documents)
        
        logger.info(
            "Retrieved Context:\n%s",
            context
        )

        prompt = f"""
You are an expert Site Reliability Engineer.

Use ONLY the information present in the context.

Do not make assumptions.
Do not add Kubernetes knowledge that is not in the context.
If the answer cannot be found in the context say:

"I could not find relevant information in the runbooks."

Context:
{context}

Question:
{question}

Answer:
"""

        answer = self.llm.generate(
            prompt=prompt
        )

        return answer