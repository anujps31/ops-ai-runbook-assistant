from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.document_loader import load_directory_recursive
from app.services.text_cleaner import clean_text
from app.services.chunking_service import chunk_documents
from app.services.embedding_service import embed_chunks
from app.services.chroma_service import ChromaService

from app.utils.logger import get_logger

logger = get_logger(__name__)


def main():

    docs = load_directory_recursive(project_root / "data")

    for doc in docs:
        doc["content"] = clean_text(doc["content"])

    chunks = chunk_documents(
        docs,
        chunk_size=100,
        chunk_overlap=20,
    )

    embedded_chunks = embed_chunks(chunks)

    chroma = ChromaService()

    chroma.reset()

    stored = chroma.add_chunks(embedded_chunks)

    logger.info("Stored chunks: %d", stored)

    logger.info("Collection count: %d", chroma.count())


if __name__ == "__main__":
    main()