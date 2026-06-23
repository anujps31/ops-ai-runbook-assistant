"""
Test document loader and text cleaner pipeline

This script validates the document ingestion pipeline by:
  1. Loading all documents from ./data recursively
  2. Cleaning each document with text_cleaner
  3. Reporting statistics on original vs. cleaned sizes
  4. Logging the entire process

Run from project root:
  python scripts/test_loader.py

This is a diagnostic tool for operators and developers to verify that the
RAG knowledge base is being loaded and cleaned correctly.

"""

import sys
from pathlib import Path

# Add project root to path so we can import app modules
# This allows the script to run from any directory
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.utils.logger import get_logger
from app.services.document_loader import load_directory_recursive
from app.services.text_cleaner import clean_text


# Module logger for diagnostic output
logger = get_logger(__name__)


def main() -> int:
    """
    Main entry point for the document loader validation script.

    Returns:
        int: Exit code (0 for success, 1 for errors)
    """
    # Define the data directory to scan
    # Using Path.cwd() ensures we load from project root
    data_dir = project_root / "data"

    logger.info("=" * 80)
    logger.info("Document Loader Test Pipeline")
    logger.info("=" * 80)
    logger.info("Scanning directory: %s", data_dir)

    # Step 1: Load all documents from data directory recursively
    logger.info("Loading documents...")
    documents = load_directory_recursive(data_dir)

    if not documents:
        logger.warning("No documents found in %s", data_dir)
        return 1

    logger.info("Successfully loaded %d documents", len(documents))

    # Step 2: Process each document through cleaning pipeline
    logger.info("-" * 80)
    logger.info("Document Statistics:")
    logger.info("-" * 80)

    total_original_chars = 0
    total_cleaned_chars = 0

    for i, doc in enumerate(documents, start=1):
        # Extract document metadata
        filename = doc["filename"]
        original_content = doc["content"]
        filepath = doc["filepath"]

        # Count original size
        original_char_count = len(original_content)
        total_original_chars += original_char_count

        # Step 3: Clean the text
        cleaned_content = clean_text(original_content)

        # Count cleaned size
        cleaned_char_count = len(cleaned_content)
        total_cleaned_chars += cleaned_char_count

        # Calculate reduction percentage
        reduction_percent = (
            (original_char_count - cleaned_char_count) / original_char_count * 100
        ) if original_char_count > 0 else 0

        # Print document statistics
        logger.info(
            "[%d] %s: %d chars → %d chars (%.1f%% reduction)",
            i,
            filename,
            original_char_count,
            cleaned_char_count,
            reduction_percent,
        )

    # Step 4: Print summary statistics
    logger.info("-" * 80)
    logger.info("Summary Statistics:")
    logger.info("-" * 80)
    logger.info("Total documents: %d", len(documents))
    logger.info("Total original characters: %d", total_original_chars)
    logger.info("Total cleaned characters: %d", total_cleaned_chars)

    if total_original_chars > 0:
        total_reduction_percent = (
            (total_original_chars - total_cleaned_chars) / total_original_chars * 100
        )
        logger.info("Total reduction: %.1f%%", total_reduction_percent)

    logger.info("=" * 80)
    logger.info("Test pipeline completed successfully")
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
