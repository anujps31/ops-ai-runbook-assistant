from typing import List, Dict, Any

import chromadb

from app.utils.logger import get_logger

logger = get_logger(__name__)

COLLECTION_NAME = "runbooks"


class ChromaService:
    def __init__(self, persist_directory: str = "./data/chroma"):
        self.client = chromadb.PersistentClient(path=persist_directory)

        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME
        )

        logger.info(
            "Connected to ChromaDB collection: %s",
            COLLECTION_NAME,
        )

    def add_chunks(self, embedded_chunks: List[Dict[str, Any]]) -> int:
        if not embedded_chunks:
            return 0

        ids = []
        documents = []
        embeddings = []
        metadatas = []

        for chunk in embedded_chunks:
            ids.append(chunk["chunk_id"])
            documents.append(chunk["content"])
            embeddings.append(chunk["embedding"])

            metadatas.append(
                {
                    "filename": chunk["filename"],
                    "filepath": chunk["filepath"],
                }
            )

        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        logger.info(
            "Stored %d chunks in ChromaDB",
            len(ids),
        )

        return len(ids)

    def count(self) -> int:
        return self.collection.count()

    def reset(self):
        self.client.delete_collection(COLLECTION_NAME)

        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME
        )

        logger.info("Collection reset completed")