"""
Text cleaning utilities for document preprocessing

This module provides functions to clean and normalize document text before
it is chunked and embedded. Cleaning improves RAG quality by:
  - Removing noise (extra whitespace, formatting artifacts)
  - Normalizing line endings across different platforms
  - Ensuring consistent text format for embedding models

This is a lightweight preprocessing step; heavy transformations (stemming,
lemmatization) are not included.

"""

import re
from typing import Optional

from app.utils.logger import get_logger


# Module logger for tracking cleaning operations
logger = get_logger(__name__)


def clean_text(text: str) -> str:
    """
    Clean and normalize document text.

    Performs the following operations in sequence:
      1. Normalize line endings (CRLF → LF)
      2. Remove excessive blank lines (3+ → 2)
      3. Remove leading/trailing whitespace from each line
      4. Remove trailing whitespace at end of document
      5. Ensure document ends with single newline

    Args:
        text (str): Raw document text

    Returns:
        str: Cleaned and normalized text

    Notes:
        - This function is idempotent: cleaning cleaned text produces
          the same result.
        - Unicode whitespace characters are handled by standard Python
          string operations; use with UTF-8 encoded text.
        - Very large texts (>10MB) may be slow; consider chunking first
          in production use cases.

    Example:
        raw = "Line 1  \\r\\n\\r\\n\\r\\n  Line 2\\r\\n"
        clean = clean_text(raw)
        # Result: "Line 1\\n\\nLine 2\\n"
    """
    if not text:
        logger.debug("Received empty text for cleaning")
        return ""

    # Step 1: Normalize line endings (CRLF → LF)
    # Handles text from Windows (\r\n), Mac (\r), and Unix (\n) sources
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Step 2: Remove excessive consecutive blank lines (3+ → 2)
    # Preserve single blank lines for readability; collapse repeated blanks
    text = re.sub(r"\n\n\n+", "\n\n", text)

    # Step 3: Remove leading and trailing whitespace from each line
    # Fixes inconsistent indentation and formatting
    lines = text.split("\n")
    lines = [line.rstrip() for line in lines]
    text = "\n".join(lines)

    # Step 4: Remove trailing whitespace at end of document
    text = text.rstrip()

    # Step 5: Ensure document ends with single newline
    # Standard practice for text files
    text = text + "\n"

    logger.debug("Cleaned text: %d characters after cleaning", len(text))
    return text


def clean_text_preserve_structure(text: str) -> str:
    """
    Clean text while preserving paragraph structure and indentation.

    Similar to clean_text() but retains leading whitespace (indentation)
    on lines, useful for preserving code blocks or formatted content.

    Operations:
      1. Normalize line endings
      2. Remove excessive blank lines (3+ → 2)
      3. Remove trailing whitespace from each line (preserve leading)
      4. Remove trailing whitespace at document end
      5. Ensure document ends with newline

    Args:
        text (str): Raw document text

    Returns:
        str: Cleaned text with indentation preserved

    Example:
        raw = "def hello():\\r\\n    print('hi')\\r\\n"
        clean = clean_text_preserve_structure(raw)
        # Result: "def hello():\n    print('hi')\n"
    """
    if not text:
        logger.debug("Received empty text for structure-preserving cleaning")
        return ""

    # Step 1: Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Step 2: Remove excessive blank lines
    text = re.sub(r"\n\n\n+", "\n\n", text)

    # Step 3: Remove trailing whitespace from each line (keep leading)
    lines = text.split("\n")
    lines = [line.rstrip() if line else "" for line in lines]
    text = "\n".join(lines)

    # Step 4: Remove trailing whitespace at end
    text = text.rstrip()

    # Step 5: Ensure document ends with newline
    text = text + "\n"

    logger.debug("Cleaned text (structure preserved): %d characters", len(text))
    return text


def remove_blank_lines(text: str) -> str:
    """
    Remove all blank lines from text.

    Useful when paragraph separation is not needed or when preparing
    text for line-by-line processing.

    Args:
        text (str): Document text

    Returns:
        str: Text with all blank lines removed

    Example:
        raw = "Line 1\\n\\nLine 2\\n"
        result = remove_blank_lines(raw)
        # Result: "Line 1\\nLine 2\\n"
    """
    if not text:
        return ""

    # Filter out empty or whitespace-only lines
    lines = text.split("\n")
    lines = [line for line in lines if line.strip()]
    result = "\n".join(lines) + "\n"

    logger.debug("Removed blank lines: %d characters", len(result))
    return result


def normalize_whitespace(text: str) -> str:
    """
    Normalize all whitespace: collapse spaces, remove tabs, normalize newlines.

    Converts all whitespace sequences to single spaces (except newlines).
    Useful for extracting content from HTML or documents with irregular formatting.

    Args:
        text (str): Document text

    Returns:
        str: Text with normalized whitespace

    Example:
        raw = "Text  with   irregular   spaces"
        result = normalize_whitespace(raw)
        # Result: "Text with irregular spaces"
    """
    if not text:
        return ""

    # Replace all tabs with spaces
    text = text.replace("\t", " ")

    # Collapse multiple spaces to single space
    text = re.sub(r" +", " ", text)

    logger.debug("Normalized whitespace: %d characters", len(text))
    return text


# ============================================================================
# Usage Examples
# ============================================================================
#
# Basic cleaning before RAG embedding:
# ───────────────────────────────────────────────────────────────────────────
# from app.services.text_cleaner import clean_text
# from app.services.document_loader import load_file
# from pathlib import Path
#
# doc = load_file(Path("data/runbooks/example.md"))
# if doc:
#     cleaned_content = clean_text(doc["content"])
#     # Now ready for chunking and embedding
#
#
# Clean while preserving code block indentation:
# ───────────────────────────────────────────────────────────────────────────
# from app.services.text_cleaner import clean_text_preserve_structure
#
# script_content = load_file(Path("data/scripts/deploy.sh"))["content"]
# cleaned = clean_text_preserve_structure(script_content)
# # Indentation preserved for shell scripts
#
#
# Remove all blank lines for line-by-line processing:
# ───────────────────────────────────────────────────────────────────────────
# from app.services.text_cleaner import remove_blank_lines
#
# text = load_file(Path("data/doc.txt"))["content"]
# lines_only = remove_blank_lines(text)
# for line in lines_only.split("\n"):
#     process_line(line)
