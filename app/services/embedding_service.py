"""
Embedding service for RAG pipeline

This module generates embeddings for document chunks using Ollama's local
embedding API. Embeddings are dense vector representations of text that
capture semantic meaning, enabling similarity-based retrieval.

Design:
  - Calls local Ollama embedding API (/api/embeddings)
  - Uses model: nomic-embed-text (384-dimensional embeddings)
  - Handles network errors and API failures gracefully
  - Supports single text or batch embedding of chunks

Ollama setup:
  - Download model: `ollama pull nomic-embed-text`
  - Run server: `ollama serve` (listens on http://localhost:11434)
  - Verify: curl http://localhost:11434/api/tags

This module handles embedding generation only; vector storage and retrieval
are separate concerns (handled by ChromaDB or similar).

"""

from typing import List, Dict, Any, Optional, Tuple

import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

from app.utils.logger import get_logger
from app.utils.config import settings


# Module logger for tracking embedding operations
logger = get_logger(__name__)


# Ollama embedding model to use
EMBEDDING_MODEL = "nomic-embed-text"

# Ollama API endpoint for embeddings
OLLAMA_EMBEDDINGS_ENDPOINT = f"{settings.OLLAMA_BASE_URL}/api/embeddings"

# Request timeout in seconds (embedding API can be slow for large texts)
REQUEST_TIMEOUT = 60

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds


def embed_text(text: str, retry_count: int = 0) -> Optional[List[float]]:
    """
    Generate embedding for a single text string using Ollama.

    Args:
        text (str): Text to embed
        retry_count (int): Internal retry counter (do not set manually)

    Returns:
        Optional[List[float]]: Embedding vector (list of floats), or None if failed

    Notes:
        - Returns 384-dimensional vector (nomic-embed-text model)
        - Empty text returns None (logged as warning)
        - Network errors are retried up to MAX_RETRIES times
        - API errors are logged and None is returned

    Example:
        embedding = embed_text("Database failover procedure")
        if embedding:
            print(f"Embedding dimension: {len(embedding)}")
    """
    if not text or not text.strip():
        logger.warning("Cannot embed empty text")
        return None

    try:
        # Log embedding request
        logger.debug("Requesting embedding from Ollama for text (%d chars)", len(text))

        # Prepare request payload
        payload = {
            "model": EMBEDDING_MODEL,
            "prompt": text,
        }

        # Call Ollama embedding API
        response = requests.post(
            OLLAMA_EMBEDDINGS_ENDPOINT,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )

        # Check for HTTP errors
        response.raise_for_status()

        # Extract embedding from response
        data = response.json()
        embedding = data.get("embedding")

        if not embedding:
            logger.error("Ollama returned empty embedding for text")
            return None

        logger.debug("Successfully generated embedding (dimension: %d)", len(embedding))
        return embedding

    except Timeout:
        # Request timed out
        logger.warning("Ollama embedding request timed out (%ds)", REQUEST_TIMEOUT)

        # Retry with backoff
        if retry_count < MAX_RETRIES:
            logger.info("Retrying embedding request (attempt %d/%d)", retry_count + 1, MAX_RETRIES)
            return embed_text(text, retry_count + 1)
        else:
            logger.error("Max retries exceeded for embedding request")
            return None

    except ConnectionError as e:
        # Cannot connect to Ollama service
        logger.error(
            "Cannot connect to Ollama at %s — ensure ollama serve is running",
            settings.OLLAMA_BASE_URL,
        )
        return None

    except RequestException as e:
        # Other HTTP request errors (4xx, 5xx, etc.)
        logger.error("Ollama API error: %s", str(e))
        return None

    except Exception as e:
        # Unexpected errors
        logger.exception("Unexpected error during embedding: %s", str(e))
        return None


def embed_chunk(chunk: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Generate embedding for a single document chunk.

    Args:
        chunk (Dict[str, Any]): Chunk dictionary with keys:
            - chunk_id (str): Unique chunk identifier
            - filename (str): Source document filename
            - filepath (str): Source document filepath
            - content (str): Chunk text content
            - chunk_size (int): Size of chunk in characters

    Returns:
        Optional[Dict[str, Any]]: Chunk with embedding added, or None if failed.
        Structure:
            {
                "chunk_id": str,
                "filename": str,
                "filepath": str,
                "content": str,
                "chunk_size": int,
                "embedding": List[float]  # New field added
            }

    Notes:
        - Adds "embedding" field to chunk dictionary
        - Returns None only if embedding generation fails (not if chunk is invalid)
        - Empty chunks are skipped (logged as debug)

    Example:
        chunk = {
            "chunk_id": "doc_1",
            "filename": "doc.md",
            "filepath": "/path/doc.md",
            "content": "Important text",
            "chunk_size": 15
        }
        result = embed_chunk(chunk)
        if result:
            print(f"Embedding added to {result['chunk_id']}")
    """
    # Validate chunk structure
    try:
        chunk_id = chunk.get("chunk_id", "unknown")
        content = chunk.get("content", "")
    except (AttributeError, KeyError) as e:
        logger.error("Invalid chunk structure: %s", str(e))
        return None

    # Skip empty chunks
    if not content or not content.strip():
        logger.debug("Skipping empty chunk: %s", chunk_id)
        return None

    # Generate embedding for chunk content
    embedding = embed_text(content)

    if embedding is None:
        logger.warning("Failed to generate embedding for chunk %s", chunk_id)
        return None

    # Add embedding to chunk
    chunk_with_embedding = {
        **chunk,
        "embedding": embedding,
    }

    logger.debug("Added embedding to chunk %s (dimension: %d)", chunk_id, len(embedding))
    return chunk_with_embedding


def embed_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Generate embeddings for multiple document chunks in batch.

    Args:
        chunks (List[Dict[str, Any]]): List of chunk dictionaries

    Returns:
        List[Dict[str, Any]]: Chunks with embeddings added.
        Chunks that fail to embed are skipped (logged as warning).

    Notes:
        - Processes chunks sequentially (respects Ollama rate limits)
        - If one chunk fails, processing continues with others (graceful failure)
        - Consider adding progress logging for large batches
        - For very large batches (1000+), monitor memory and Ollama load

    Example:
        chunks = [
            {"chunk_id": "doc_1", "filename": "...", "content": "..."},
            {"chunk_id": "doc_2", "filename": "...", "content": "..."}
        ]
        embedded = embed_chunks(chunks)
        print(f"Successfully embedded {len(embedded)}/{len(chunks)} chunks")
    """
    if not chunks:
        logger.debug("No chunks to embed")
        return []

    logger.info("Embedding %d chunks...", len(chunks))

    embedded_chunks = []
    failed_count = 0

    # Process each chunk
    for i, chunk in enumerate(chunks, start=1):
        try:
            # Attempt to embed the chunk
            chunk_with_embedding = embed_chunk(chunk)

            if chunk_with_embedding is not None:
                embedded_chunks.append(chunk_with_embedding)
            else:
                failed_count += 1

            # Log progress every 10 chunks
            if i % 10 == 0 or i == len(chunks):
                logger.info("Progress: %d/%d chunks embedded", i, len(chunks))

        except Exception as e:
            # Log error but continue processing
            logger.exception(
                "Unexpected error embedding chunk %s: %s",
                chunk.get("chunk_id", "unknown"),
                str(e),
            )
            failed_count += 1

    logger.info(
        "Completed embedding: %d successful, %d failed out of %d chunks",
        len(embedded_chunks),
        failed_count,
        len(chunks),
    )

    return embedded_chunks


def verify_ollama_connection() -> bool:
    """
    Verify that Ollama service is running and accessible.

    Returns:
        bool: True if Ollama is reachable, False otherwise

    Notes:
        - Useful for startup checks and health probes
        - Logs connection status at info level
        - Does not require model to be loaded

    Example:
        if verify_ollama_connection():
            logger.info("Ollama service is ready")
        else:
            logger.error("Ollama service is not responding")
    """
    try:
        # Call Ollama tags endpoint to check if service is running
        response = requests.get(
            f"{settings.OLLAMA_BASE_URL}/api/tags",
            timeout=5,
        )
        response.raise_for_status()

        logger.info("✓ Ollama service is running at %s", settings.OLLAMA_BASE_URL)
        return True

    except ConnectionError:
        logger.error("✗ Cannot connect to Ollama at %s", settings.OLLAMA_BASE_URL)
        return False

    except Timeout:
        logger.error("✗ Ollama service at %s is not responding", settings.OLLAMA_BASE_URL)
        return False

    except Exception as e:
        logger.error("✗ Error checking Ollama connection: %s", str(e))
        return False


# ============================================================================
# Usage Examples
# ============================================================================
#
# Embed a single text:
# ───────────────────────────────────────────────────────────────────────────
# from app.services.embedding_service import embed_text
#
# embedding = embed_text("This is important content")
# if embedding:
#     print(f"Embedding dimension: {len(embedding)}")
#     print(f"First 5 values: {embedding[:5]}")
#
#
# Embed document chunks (full pipeline):
# ───────────────────────────────────────────────────────────────────────────
# from app.services.document_loader import load_directory_recursive
# from app.services.text_cleaner import clean_text
# from app.services.chunking_service import chunk_documents
# from app.services.embedding_service import embed_chunks, verify_ollama_connection
# from pathlib import Path
#
# # Verify Ollama is running
# if not verify_ollama_connection():
#     raise RuntimeError("Ollama service is not available")
#
# # Load documents
# docs = load_directory_recursive(Path("data"))
# for doc in docs:
#     doc["content"] = clean_text(doc["content"])
#
# # Chunk documents
# chunks = chunk_documents(docs, chunk_size=1500, chunk_overlap=300)
#
# # Embed chunks
# embedded_chunks = embed_chunks(chunks)
#
# # Next: Store embeddings in ChromaDB
# print(f"Embedded {len(embedded_chunks)} chunks, ready for vector storage")
#
#
# Check Ollama before starting RAG pipeline:
# ───────────────────────────────────────────────────────────────────────────
# from app.services.embedding_service import verify_ollama_connection
#
# @app.on_event("startup")
# async def startup():
#     if not verify_ollama_connection():
#         logger.warning("Ollama not available at startup")
