from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.retrieval_service import RetrievalService
from app.utils.logger import get_logger

logger = get_logger(__name__)


def main():
    retriever = RetrievalService()

    queries = [
        "API returning 503 errors",
        "Pod restarting continuously",
        "P1 incident bridge call"
    ]

    for query in queries:
        logger.info("=" * 80)
        logger.info("Query: %s", query)

        results = retriever.search(query)

        print(results)


if __name__ == "__main__":
    main()