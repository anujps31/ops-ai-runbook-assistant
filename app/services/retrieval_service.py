from app.services.embedding_service import embed_text
from app.services.chroma_service import ChromaService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RetrievalService:

    def __init__(self):
        self.chroma = ChromaService()

    def search(
        self,
        query: str,
        top_k: int = 2
    ):
        logger.info(f"Searching for query: {query}")

        query_embedding = embed_text(query)

        results = self.chroma.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )

        logger.info(
            f"Retrieved {len(results.get('ids', [[]])[0])} chunks"
        )

        return results