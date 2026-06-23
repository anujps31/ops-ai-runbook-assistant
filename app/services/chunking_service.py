"""
Document chunking service for RAG pipeline

This module splits documents into smaller chunks suitable for embedding and
retrieval. Chunking allows long documents to be retrieved with high relevance
since relevant passages fit within chunk boundaries.

Design:
  - Fixed character-based chunking (simple, deterministic)
  - Configurable chunk size and overlap
  - Overlap between chunks preserves context across boundaries
  - Each chunk receives a unique ID for tracking through the pipeline

Chunking strategy:
  - Split text on character boundaries (no token awareness)
  - Maintain overlap between adjacent chunks
  - Example: 100-char chunks with 20-char overlap:
    Chunk 1: [0-100]
    Chunk 2: [80-180]  (overlaps with Chunk 1 on [80-100])
    Chunk 3: [160-260]

This module handles chunking only; embedding and vector storage are
separate concerns.

"""

from typing import List, Dict, Any, Optional

from app.utils.logger import get_logger


# Module logger for tracking chunking operations
logger = get_logger(__name__)


# Default chunk parameters (can be overridden per call)
DEFAULT_CHUNK_SIZE = 1000  # characters per chunk
DEFAULT_CHUNK_OVERLAP = 200  # characters of overlap between chunks


def chunk_document(
    document: Dict[str, Any],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[Dict[str, Any]]:
    """
    Split a single document into chunks.

    Args:
        document (Dict[str, Any]): Document dictionary with keys:
            - filename (str): Document filename
            - filepath (str): Full file path
            - content (str): Document content to chunk
        chunk_size (int): Target chunk size in characters (default: 1000)
        chunk_overlap (int): Overlap between consecutive chunks (default: 200)

    Returns:
        List[Dict[str, Any]]: List of chunk dictionaries, each containing:
            - chunk_id (str): Unique identifier "filename_N"
            - filename (str): Source document filename
            - filepath (str): Source document filepath
            - content (str): Chunk text content
            - chunk_size (int): Actual size of this chunk in characters

    Raises:
        No exceptions raised; errors are logged and empty list returned

    Validation:
        - chunk_size must be > 0; defaults to DEFAULT_CHUNK_SIZE if invalid
        - chunk_overlap must be >= 0 and < chunk_size; capped if invalid
        - Empty documents return empty chunk list

    Notes:
        - Chunking is deterministic: same input always produces same chunks
        - Overlap preserves context across chunk boundaries (important for RAG)
        - Very large documents produce many chunks; consider monitoring
        - Character-based chunking doesn't respect word/line boundaries

    Example:
        doc = {
            "filename": "runbook.md",
            "filepath": "/path/to/runbook.md",
            "content": "Long text..."
        }
        chunks = chunk_document(doc, chunk_size=500, chunk_overlap=100)
        print(f"Created {len(chunks)} chunks")
    """
    # Validate and extract document fields
    try:
        filename = document.get("filename", "unknown")
        filepath = document.get("filepath", "unknown")
        content = document.get("content", "")
    except (AttributeError, KeyError) as e:
        logger.error("Invalid document structure: %s", str(e))
        return []

    # Validate chunk parameters
    if chunk_size <= 0:
        logger.warning("Invalid chunk_size %d, using default %d", chunk_size, DEFAULT_CHUNK_SIZE)
        chunk_size = DEFAULT_CHUNK_SIZE

    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        logger.warning(
            "Invalid chunk_overlap %d (must be >= 0 and < %d), using default %d",
            chunk_overlap,
            chunk_size,
            DEFAULT_CHUNK_OVERLAP,
        )
        chunk_overlap = DEFAULT_CHUNK_OVERLAP

    # Handle empty content
    if not content:
        logger.debug("Document %s is empty, no chunks created", filename)
        return []

    # Log chunking operation
    logger.info(
        "Chunking %s (%d chars) with size=%d overlap=%d",
        filename,
        len(content),
        chunk_size,
        chunk_overlap,
    )

    chunks = []
    content_length = len(content)
    chunk_count = 0

    # Create chunks with overlap
    # Step size is (chunk_size - overlap) to achieve desired overlap
    step_size = chunk_size - chunk_overlap

    for start_idx in range(0, content_length, step_size):
        # End index for this chunk
        end_idx = min(start_idx + chunk_size, content_length)

        # Extract chunk text
        chunk_text = content[start_idx:end_idx]

        # Skip empty chunks
        if not chunk_text.strip():
            continue

        chunk_count += 1

        # Create chunk dictionary with metadata
        chunk = {
            "chunk_id": f"{filename}_{chunk_count}",
            "filename": filename,
            "filepath": filepath,
            "content": chunk_text,
            "chunk_size": len(chunk_text),
        }

        chunks.append(chunk)

        # Stop if we've consumed entire content
        if end_idx >= content_length:
            break

    logger.info("Created %d chunks from %s", len(chunks), filename)
    return chunks


def chunk_documents(
    documents: List[Dict[str, Any]],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[Dict[str, Any]]:
    """
    Chunk multiple documents in a batch.

    Args:
        documents (List[Dict[str, Any]]): List of document dictionaries
        chunk_size (int): Target chunk size in characters (default: 1000)
        chunk_overlap (int): Overlap between consecutive chunks (default: 200)

    Returns:
        List[Dict[str, Any]]: Flattened list of all chunks from all documents

    Notes:
        - Documents are processed sequentially
        - If one document fails, processing continues with others (graceful failure)
        - Chunk IDs are unique within each document but may overlap across documents
        - Consider adding document-level uniqueness to chunk_id if needed

    Example:
        docs = [
            {"filename": "doc1.md", "filepath": "...", "content": "..."},
            {"filename": "doc2.md", "filepath": "...", "content": "..."}
        ]
        all_chunks = chunk_documents(docs, chunk_size=800)
        print(f"Total chunks: {len(all_chunks)}")
    """
    if not documents:
        logger.debug("No documents to chunk")
        return []

    logger.info("Chunking %d documents with size=%d overlap=%d", len(documents), chunk_size, chunk_overlap)

    all_chunks = []

    # Process each document
    for doc in documents:
        try:
            # Chunk the individual document
            doc_chunks = chunk_document(doc, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            all_chunks.extend(doc_chunks)

        except Exception as e:
            # Log error but continue processing other documents
            logger.exception("Error chunking document %s: %s", doc.get("filename", "unknown"), str(e))
            continue

    logger.info("Completed chunking: %d total chunks from %d documents", len(all_chunks), len(documents))
    return all_chunks


# ============================================================================
# Usage Examples
# ============================================================================
#
# Chunk a single document:
# ───────────────────────────────────────────────────────────────────────────
# from app.services.document_loader import load_file
# from app.services.text_cleaner import clean_text
# from app.services.chunking_service import chunk_document
# from pathlib import Path
#
# doc = load_file(Path("data/runbooks/example.md"))
# if doc:
#     doc["content"] = clean_text(doc["content"])
#     chunks = chunk_document(doc, chunk_size=1000, chunk_overlap=200)
#     for chunk in chunks:
#         print(f"{chunk['chunk_id']}: {len(chunk['content'])} chars")
#
#
# Chunk multiple documents (full pipeline):
# ───────────────────────────────────────────────────────────────────────────
# from app.services.document_loader import load_directory_recursive
# from app.services.text_cleaner import clean_text
# from app.services.chunking_service import chunk_documents
# from pathlib import Path
#
# docs = load_directory_recursive(Path("data"))
#
# # Clean all documents
# for doc in docs:
#     doc["content"] = clean_text(doc["content"])
#
# # Chunk all documents
# chunks = chunk_documents(docs, chunk_size=1500, chunk_overlap=300)
# print(f"Created {len(chunks)} chunks from {len(docs)} documents")
#
# # Next: embed chunks and store in ChromaDB
#
#
# Custom chunk sizes for different document types:
# ───────────────────────────────────────────────────────────────────────────
# # Small chunks for dense technical docs
# tech_chunks = chunk_documents(tech_docs, chunk_size=500, chunk_overlap=100)
#
# # Larger chunks for narrative docs
# narrative_chunks = chunk_documents(narrative_docs, chunk_size=2000, chunk_overlap=400)
