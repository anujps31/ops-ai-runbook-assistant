"""
Test document chunking pipeline

This script validates the RAG document chunking pipeline by:
  1. Loading all documents from ./data recursively
  2. Cleaning each document with text_cleaner
  3. Chunking documents with configurable parameters
  4. Reporting detailed statistics on chunks
  5. Logging the entire process

Run from project root:
  python scripts/test_chunking.py

This is a diagnostic tool for developers to verify that documents are being
chunked correctly and that chunk boundaries preserve meaningful content.

"""

import sys
from pathlib import Path

# Add project root to path so we can import app modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.utils.logger import get_logger
from app.services.document_loader import load_directory_recursive
from app.services.text_cleaner import clean_text
from app.services.chunking_service import chunk_documents


# Module logger for diagnostic output
logger = get_logger(__name__)


# Chunking parameters for this test
CHUNK_SIZE = 100  # Small for testing purposes
CHUNK_OVERLAP = 20  # 20% overlap between chunks


def main() -> int:
    """
    Main entry point for the document chunking test pipeline.

    Returns:
        int: Exit code (0 for success, 1 for errors)
    """
    # Define the data directory to scan
    data_dir = project_root / "data"

    logger.info("=" * 80)
    logger.info("Document Chunking Test Pipeline")
    logger.info("=" * 80)
    logger.info("Data directory: %s", data_dir)
    logger.info("Chunk size: %d characters", CHUNK_SIZE)
    logger.info("Chunk overlap: %d characters", CHUNK_OVERLAP)

    # Step 1: Load all documents from data directory recursively
    logger.info("-" * 80)
    logger.info("Step 1: Loading documents...")
    logger.info("-" * 80)

    documents = load_directory_recursive(data_dir)

    if not documents:
        logger.warning("No documents found in %s", data_dir)
        return 1

    logger.info("✓ Successfully loaded %d documents", len(documents))

    # Step 2: Clean all documents
    logger.info("-" * 80)
    logger.info("Step 2: Cleaning documents...")
    logger.info("-" * 80)

    cleaned_docs = []
    for doc in documents:
        # Clean the document content
        cleaned_content = clean_text(doc["content"])

        # Create a new document dict with cleaned content
        cleaned_doc = {
            "filename": doc["filename"],
            "filepath": doc["filepath"],
            "content": cleaned_content,
        }
        cleaned_docs.append(cleaned_doc)

    logger.info("✓ Cleaned %d documents", len(cleaned_docs))

    # Step 3: Chunk all documents
    logger.info("-" * 80)
    logger.info("Step 3: Chunking documents...")
    logger.info("-" * 80)

    chunks = chunk_documents(cleaned_docs, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)

    if not chunks:
        logger.warning("No chunks created from documents")
        return 1

    logger.info("✓ Successfully created %d chunks", len(chunks))

    # Step 4: Print detailed chunk statistics
    logger.info("-" * 80)
    logger.info("Chunk Statistics:")
    logger.info("-" * 80)

    # Group chunks by filename for better organization
    chunks_by_file = {}
    for chunk in chunks:
        filename = chunk["filename"]
        if filename not in chunks_by_file:
            chunks_by_file[filename] = []
        chunks_by_file[filename].append(chunk)

    total_chunk_chars = 0

    # Iterate through chunks organized by source file
    for filename, file_chunks in sorted(chunks_by_file.items()):
        logger.info("")
        logger.info("File: %s (%d chunks)", filename, len(file_chunks))
        logger.info("-" * 40)

        for i, chunk in enumerate(file_chunks, start=1):
            # Extract chunk metadata
            chunk_id = chunk["chunk_id"]
            chunk_size = chunk["chunk_size"]
            chunk_content = chunk["content"]

            # Track total characters
            total_chunk_chars += chunk_size

            # Get first 100 characters (or less if chunk is smaller)
            preview = chunk_content[:100]

            # Replace newlines with spaces for readability in log
            preview = preview.replace("\n", " ")

            # Truncate preview if it's longer than display width
            if len(preview) == 100 and len(chunk_content) > 100:
                preview = preview + "..."

            # Log chunk information
            logger.info(
                "  [%d] chunk_id=%s | size=%d chars | preview: %s",
                i,
                chunk_id,
                chunk_size,
                preview,
            )

    # Step 5: Print summary statistics
    logger.info("")
    logger.info("-" * 80)
    logger.info("Summary Statistics:")
    logger.info("-" * 80)
    logger.info("Total documents loaded: %d", len(documents))
    logger.info("Total documents cleaned: %d", len(cleaned_docs))
    logger.info("Total chunks created: %d", len(chunks))
    logger.info("Total chunk characters: %d", total_chunk_chars)

    # Calculate average chunk size
    avg_chunk_size = total_chunk_chars / len(chunks) if chunks else 0
    logger.info("Average chunk size: %.1f characters", avg_chunk_size)

    # Calculate chunks per document
    chunks_per_doc = len(chunks) / len(documents) if documents else 0
    logger.info("Average chunks per document: %.1f", chunks_per_doc)

    # Calculate compression from original to chunks
    original_total = sum(len(doc["content"]) for doc in documents)
    if original_total > 0:
        compression_percent = (original_total - total_chunk_chars) / original_total * 100
        logger.info("Size change from original: %.1f%% (%.0f → %.0f chars)", 
                    -compression_percent if compression_percent > 0 else compression_percent,
                    original_total, total_chunk_chars)

    logger.info("=" * 80)
    logger.info("✓ Chunking test pipeline completed successfully")
    logger.info("=" * 80)

    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        # Catch any unexpected errors and log them
        logger.exception("Unexpected error during test pipeline: %s", str(e))
        sys.exit(1)
