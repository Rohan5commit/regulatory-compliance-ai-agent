from __future__ import annotations

import uuid
from typing import Any

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams


class ComplianceVectorStore:
    COLLECTION_NAME = "regulations"
    VECTOR_SIZE = 384

    def __init__(self, host: str, port: int, nlp_models):
        self.client = QdrantClient(host=host, port=port)
        self.nlp_models = nlp_models
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        collections = self.client.get_collections().collections
        if any(c.name == self.COLLECTION_NAME for c in collections):
            return

        self.client.create_collection(
            collection_name=self.COLLECTION_NAME,
            vectors_config=VectorParams(size=self.VECTOR_SIZE, distance=Distance.COSINE),
        )
        logger.info("Created Qdrant collection {}", self.COLLECTION_NAME)

    def add_regulation(self, regulation_id: int, text: str, metadata: dict[str, Any]) -> str:
        embedding = self.nlp_models.get_sentence_embedding(text)
        point_id = str(uuid.uuid4())

        point = PointStruct(
            id=point_id,
            vector=embedding,
            payload={
                "regulation_id": regulation_id,
                "text": (text or "")[:1200],
                "title": metadata.get("title"),
                "regulator": metadata.get("regulator"),
                "effective_date": str(metadata.get("effective_date")) if metadata.get("effective_date") else None,
                "document_type": metadata.get("document_type"),
            },
        )

        self.client.upsert(collection_name=self.COLLECTION_NAME, points=[point])
        return point_id

    def semantic_search(self, query: str, limit: int = 10, filter_dict: Any = None) -> list[dict[str, Any]]:
        query_embedding = self.nlp_models.get_sentence_embedding(query)
        hits = self.client.search(
            collection_name=self.COLLECTION_NAME,
            query_vector=query_embedding,
            limit=limit,
            query_filter=filter_dict,
        )

        return [
            {
                "regulation_id": hit.payload.get("regulation_id"),
                "score": hit.score,
                "title": hit.payload.get("title"),
                "text_snippet": hit.payload.get("text"),
                "regulator": hit.payload.get("regulator"),
            }
            for hit in hits
        ]
