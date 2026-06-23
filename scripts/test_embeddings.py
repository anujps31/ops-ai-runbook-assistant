"""
Test script for RAG embedding pipeline

This script validates the complete embedding layer of the RAG pipeline:
  1. Verify Ollama connection (service availability)
  2. Load documents recursively from data/
  3. Clean documents (normalize text)
  4. Chunk documents (character-based with overlap)
  5. Generate embeddings (Ollama nomic-embed-text model)

Output includes:
  - Summary statistics (documents, chunks, embeddings, dimensions)
  - Per-chunk details (chunk_id, filename, first 5 embedding values)

This validates end-to-end embedding generation before storage/retrieval.

Usage:
  python scripts/test_embeddings.py

Exit codes:
  0 = Success (all chunks embedded)
  1 = Failure (no documents, embedding errors, Ollama unavailable)
"""

from pathlib import Path
import sys
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sys import exit
from typing import List, Dict, Any

# Import pipeline services
from app.services.document_loader import load_directory_recursive
from app.services.text_cleaner import clean_text
from app.services.chunking_service import chunk_documents
from app.services.embedding_service import (
    embed_chunks,
    verify_ollama_connection,
)

# Import logger for tracking test execution
from app.utils.logger import get_logger


# Create module logger for test output
logger = get_logger(__name__)


def main() -> int:
    """
    Execute complete RAG embedding pipeline test.
    
    Returns:
        0 if embedding successful
        1 if any step fails
    """
    logger.info("=" * 80)
    logger.info("RAG EMBEDDING PIPELINE TEST")
    logger.info("=" * 80)
    
    # ========================================================================
    # STEP 1: Verify Ollama Connection
    # ========================================================================
    logger.info("\n[STEP 1] Verifying Ollama connection...")
    if not verify_ollama_connection():
        logger.error("❌ Ollama not available!")
        logger.error("   Please run: ollama serve")
        logger.error("   And download model: ollama pull nomic-embed-text")
        return 1
    logger.info("✓ Ollama connection verified")
    
    # ========================================================================
    # STEP 2: Load Documents Recursively
    # ========================================================================
    # Define data directory containing documents (.txt, .md files)
    data_dir = Path(__file__).parent.parent / "data"
    logger.info(f"\n[STEP 2] Loading documents from {data_dir}...")
    
    # Load all documents recursively from data/ subdirectories
    # Returns list of dicts with: {filename, filepath, content}
    documents = load_directory_recursive(data_dir)
    
    if not documents:
        logger.warning("⚠ No documents found in data/")
        return 1
    
    logger.info(f"✓ Loaded {len(documents)} documents")
    for doc in documents:
        original_size = len(doc["content"])
        logger.debug(f"  - {doc['filename']}: {original_size:,} characters")
    
    # ========================================================================
    # STEP 3: Clean Documents
    # ========================================================================
    # Clean each document's text content (normalize line endings, remove
    # excessive blank lines, trim whitespace)
    logger.info(f"\n[STEP 3] Cleaning documents...")
    total_original_chars = 0
    total_cleaned_chars = 0
    
    for doc in documents:
        original_content = doc["content"]
        total_original_chars += len(original_content)
        
        # Apply text cleaning (normalizes whitespace, blank lines, encoding)
        doc["content"] = clean_text(original_content)
        total_cleaned_chars += len(doc["content"])
        
        reduction = len(original_content) - len(doc["content"])
        reduction_pct = (reduction / len(original_content) * 100) if original_content else 0
        logger.debug(f"  - {doc['filename']}: {reduction:,} chars removed ({reduction_pct:.1f}%)")
    
    logger.info(f"✓ Cleaned documents")
    logger.info(f"  Total: {total_original_chars:,} → {total_cleaned_chars:,} characters")
    logger.info(f"  Reduction: {total_original_chars - total_cleaned_chars:,} chars ({(1 - total_cleaned_chars/total_original_chars)*100:.1f}%)")
    
    # ========================================================================
    # STEP 4: Chunk Documents
    # ========================================================================
    # Split cleaned documents into overlapping chunks suitable for embedding
    # chunk_size=100: each chunk ~100 characters
    # chunk_overlap=20: 20 character overlap between consecutive chunks
    chunk_size = 100
    chunk_overlap = 20
    
    logger.info(f"\n[STEP 4] Chunking documents (size={chunk_size}, overlap={chunk_overlap})...")
    
    # Batch chunk all documents
    # Returns list of chunk dicts with: {chunk_id, filename, filepath, content, chunk_size}
    chunks = chunk_documents(documents, chunk_size, chunk_overlap)
    
    if not chunks:
        logger.warning("⚠ No chunks created from documents")
        return 1
    
    logger.info(f"✓ Created {len(chunks)} chunks from {len(documents)} documents")
    
    # Analyze chunk distribution
    chunks_per_doc = {}
    for chunk in chunks:
        filename = chunk["filename"]
        chunks_per_doc[filename] = chunks_per_doc.get(filename, 0) + 1
    
    for filename, count in chunks_per_doc.items():
        logger.debug(f"  - {filename}: {count} chunks")
    
    # ========================================================================
    # STEP 5: Generate Embeddings
    # ========================================================================
    # Call Ollama embedding API for each chunk
    # Embedding model: nomic-embed-text (384-dimensional vectors)
    logger.info(f"\n[STEP 5] Generating embeddings (model: nomic-embed-text)...")
    
    # Batch embed all chunks
    # Returns chunks with new "embedding" field containing List[float]
    embedded_chunks = embed_chunks(chunks)
    
    if not embedded_chunks:
        logger.warning("⚠ No chunks were successfully embedded")
        return 1
    
    # Count successfully embedded chunks (have embedding field)
    embedded_count = sum(1 for chunk in embedded_chunks if "embedding" in chunk)
    logger.info(f"✓ Generated embeddings for {embedded_count}/{len(chunks)} chunks")
    
    if embedded_count < len(chunks):
        failed_count = len(chunks) - embedded_count
        logger.warning(f"⚠ {failed_count} chunks failed embedding (API errors)")
    
    # ========================================================================
    # SUMMARY STATISTICS
    # ========================================================================
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY STATISTICS")
    logger.info("=" * 80)
    
    # Calculate embedding dimension from first embedded chunk
    embedding_dimension = 0
    if embedded_count > 0:
        for chunk in embedded_chunks:
            if "embedding" in chunk:
                embedding_dimension = len(chunk["embedding"])
                break
    
    logger.info(f"Total documents:        {len(documents)}")
    logger.info(f"Total chunks:           {len(chunks)}")
    logger.info(f"Total embedded chunks:  {embedded_count}")
    logger.info(f"Embedding dimension:    {embedding_dimension}D")
    logger.info(f"Characters per chunk:   {chunk_size}")
    logger.info(f"Chunk overlap:          {chunk_overlap}")
    logger.info(f"Average chunks/doc:     {len(chunks) / len(documents):.1f}")
    logger.info(f"Average embedding size: {(embedding_dimension * 4) / 1024:.2f} KB per chunk")
    
    # ========================================================================
    # DETAILED OUTPUT: First 5 Embedding Values per Chunk
    # ========================================================================
    logger.info("\n" + "=" * 80)
    logger.info("CHUNK DETAILS (first 5 embedding values)")
    logger.info("=" * 80)
    
    # Group chunks by source filename for organized output
    chunks_by_file = {}
    for chunk in embedded_chunks:
        filename = chunk["filename"]
        if filename not in chunks_by_file:
            chunks_by_file[filename] = []
        chunks_by_file[filename].append(chunk)
    
    # Print per-chunk details
    for filename in sorted(chunks_by_file.keys()):
        logger.info(f"\n📄 {filename}")
        logger.info("-" * 80)
        
        for chunk in chunks_by_file[filename]:
            chunk_id = chunk.get("chunk_id", "N/A")
            content_preview = chunk["content"][:50].replace("\n", " ")
            
            if "embedding" in chunk:
                # Get first 5 values from embedding vector
                embedding = chunk["embedding"]
                first_5_values = embedding[:5]
                embedding_str = ", ".join(f"{v:.6f}" for v in first_5_values)
                
                logger.info(
                    f"  {chunk_id}: [{embedding_str}, ...] | {content_preview}"
                )
            else:
                # Chunk failed embedding generation
                logger.warning(
                    f"  {chunk_id}: [FAILED] | {content_preview}"
                )
    
    # ========================================================================
    # SUCCESS
    # ========================================================================
    logger.info("\n" + "=" * 80)
    logger.info("✓ EMBEDDING PIPELINE TEST COMPLETED SUCCESSFULLY")
    logger.info("=" * 80)
    logger.info("\nNext steps:")
    logger.info("  1. Store embeddings in ChromaDB or similar vector database")
    logger.info("  2. Implement similarity search for RAG retrieval")
    logger.info("  3. Integrate with incident analysis agents")
    logger.info("  4. Query embeddings to find relevant runbooks")
    
    return 0


if __name__ == "__main__":
    """Execute test and return appropriate exit code."""
    exit_code = main()
    exit(exit_code)
