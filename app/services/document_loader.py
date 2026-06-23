"""
Document loading service

This module provides utilities to load text documents (.txt and .md files)
from the file system. It is designed to populate the RAG knowledge base
by reading local documents.

Responsibilities:
  - Load individual files with error handling
  - Recursively scan directories for supported file types
  - Return structured document metadata (filename, filepath, content)

This module handles loading only; chunking and embedding are handled
separately by the RAG pipeline.

Supported file types:
  - .txt (plain text)
  - .md (Markdown)

"""

from pathlib import Path
from typing import List, Dict, Any, Optional

from app.utils.logger import get_logger


# Module logger for tracking file operations and errors
logger = get_logger(__name__)


# File type extensions supported by this loader
SUPPORTED_EXTENSIONS = {".txt", ".md"}


def load_file(filepath: Path) -> Optional[Dict[str, Any]]:
    """
    Load a single document file and return structured metadata.

    Args:
        filepath (Path): Absolute or relative path to the file

    Returns:
        Optional[Dict[str, Any]]: Dictionary with keys:
            - filename (str): Just the file name (e.g., "runbook.md")
            - filepath (str): Full file path as string
            - content (str): File contents as string
        Returns None if file cannot be read or is not supported.

    Raises:
        No exceptions are raised; errors are logged and None is returned
        to allow graceful handling of partial failures when loading
        directories with many files.

    Notes:
        - Files are read as UTF-8 encoded text.
        - File size is not validated; very large files may cause memory
          issues. Consider adding a size check in production.
    """
    filepath = Path(filepath)

    # Validate file exists and is a regular file (not directory)
    if not filepath.is_file():
        logger.warning("Path is not a file or does not exist: %s", filepath)
        return None

    # Validate file extension is supported
    if filepath.suffix.lower() not in SUPPORTED_EXTENSIONS:
        logger.debug("Skipping unsupported file type: %s", filepath.suffix)
        return None

    try:
        # Read file contents as UTF-8 text
        content = filepath.read_text(encoding="utf-8")

        # Log successful load with file size for observability
        logger.info("Loaded file: %s (%d bytes)", filepath.name, len(content))

        # Return structured document metadata
        return {
            "filename": filepath.name,
            "filepath": str(filepath.absolute()),
            "content": content,
        }

    except UnicodeDecodeError as e:
        # File is not valid UTF-8 text
        logger.error("File is not valid UTF-8: %s — %s", filepath, str(e))
        return None

    except OSError as e:
        # File cannot be read (permissions, I/O error, etc.)
        logger.error("Cannot read file: %s — %s", filepath, str(e))
        return None

    except Exception as e:
        # Catch unexpected errors to prevent entire load from failing
        logger.exception("Unexpected error loading file: %s", filepath)
        return None


def load_directory(directory: Path) -> List[Dict[str, Any]]:
    """
    Load all supported documents from a directory (non-recursive).

    Args:
        directory (Path): Directory path to scan

    Returns:
        List[Dict[str, Any]]: List of document dictionaries from load_file().
        If directory is empty or no files are supported, returns empty list.

    Notes:
        - Does NOT recursively scan subdirectories. Use load_directory_recursive()
          for nested scans.
        - Files are processed in arbitrary order; sorting is not guaranteed.
        - Files that fail to load are silently skipped (errors are logged).

    Example:
        docs = load_directory(Path("./data/runbooks"))
        for doc in docs:
            print(f"Loaded: {doc['filename']}")
    """
    directory = Path(directory)

    # Validate directory exists
    if not directory.is_dir():
        logger.warning("Path is not a directory or does not exist: %s", directory)
        return []

    logger.info("Scanning directory for documents: %s", directory)

    documents = []

    # Iterate over all files in the directory (not recursive)
    for filepath in directory.iterdir():
        # Skip directories; load_directory does not recurse
        if filepath.is_dir():
            continue

        # Attempt to load the file
        doc = load_file(filepath)
        if doc is not None:
            documents.append(doc)

    logger.info("Loaded %d documents from %s", len(documents), directory)
    return documents


def load_directory_recursive(directory: Path) -> List[Dict[str, Any]]:
    """
    Load all supported documents from a directory and its subdirectories.

    Args:
        directory (Path): Root directory path to scan recursively

    Returns:
        List[Dict[str, Any]]: List of document dictionaries from load_file().
        If no files are found, returns empty list.

    Notes:
        - Recursively scans all subdirectories.
        - Files that fail to load are silently skipped (errors are logged).
        - Be cautious with very deep directory trees; consider limiting depth.

    Example:
        docs = load_directory_recursive(Path("./data"))
        print(f"Loaded {len(docs)} documents total")
    """
    directory = Path(directory)

    # Validate directory exists
    if not directory.is_dir():
        logger.warning("Path is not a directory or does not exist: %s", directory)
        return []

    logger.info("Recursively scanning directory for documents: %s", directory)

    documents = []

    # rglob("*") recursively finds all files in subdirectories
    for filepath in directory.rglob("*"):
        # Skip directories
        if filepath.is_dir():
            continue

        # Attempt to load the file
        doc = load_file(filepath)
        if doc is not None:
            documents.append(doc)

    logger.info("Loaded %d documents recursively from %s", len(documents), directory)
    return documents


# ============================================================================
# Usage Examples
# ============================================================================
#
# Load a single file:
# ───────────────────────────────────────────────────────────────────────────
# from app.services.document_loader import load_file
# from pathlib import Path
#
# doc = load_file(Path("data/runbooks/database-failover.md"))
# if doc:
#     print(f"Loaded: {doc['filename']}")
#     print(f"Content length: {len(doc['content'])} characters")
#
#
# Load all runbooks from a directory:
# ───────────────────────────────────────────────────────────────────────────
# from app.services.document_loader import load_directory
# from pathlib import Path
#
# runbooks = load_directory(Path("data/runbooks"))
# for doc in runbooks:
#     print(f"Runbook: {doc['filename']} ({len(doc['content'])} chars)")
#
#
# Load all documents recursively (runbooks, SOPs, etc.):
# ───────────────────────────────────────────────────────────────────────────
# from app.services.document_loader import load_directory_recursive
# from pathlib import Path
#
# all_docs = load_directory_recursive(Path("data"))
# print(f"Total documents loaded: {len(all_docs)}")
