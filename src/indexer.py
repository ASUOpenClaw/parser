"""
Upsert / delete chunks in Qdrant.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.http.models import (
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
    Distance,
)

from .config import settings
from .chunker import Chunk

logger = logging.getLogger(__name__)

_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.qdrant_url)
    return _client


def _ensure_collection(client: QdrantClient, vector_size: int) -> None:
    """Create the chunks collection if it doesn't exist."""
    try:
        client.get_collection(settings.qdrant_collection)
    except (UnexpectedResponse, Exception):
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        logger.info("Created Qdrant collection '%s'", settings.qdrant_collection)


def delete_file_chunks(workspace_id: str, file_id: str) -> None:
    """Delete all Qdrant points for the given file."""
    client = _get_client()
    try:
        client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=Filter(
                must=[
                    FieldCondition(key="workspace_id", match=MatchValue(value=workspace_id)),
                    FieldCondition(key="file_id", match=MatchValue(value=file_id)),
                ]
            ),
        )
        logger.info("Deleted Qdrant points for file_id=%s workspace_id=%s", file_id, workspace_id)
    except UnexpectedResponse as e:
        if e.status_code == 404:
            logger.debug("Collection not found during delete (nothing to delete): %s", e)
        else:
            raise


def upsert_chunks(
    *,
    workspace_id: str,
    file_id: str,
    file_name: str,
    folder_id: str | None,
    mime_type: str,
    source: str,
    conversation_id: str | None,
    chunks: list[Chunk],
    dense_vecs: list[list[float]],
) -> int:
    """Upsert chunk points into Qdrant. Returns number of points upserted."""
    client = _get_client()

    points: list[PointStruct] = []
    for chunk, dense in zip(chunks, dense_vecs):
        payload: dict[str, Any] = {
            "workspace_id": workspace_id,
            "file_id": file_id,
            "file_name": file_name,
            "folder_id": folder_id,
            "mime_type": mime_type,
            "chunk_index": chunk.chunk_index,
            "page": chunk.page,
            "section": chunk.section,
            "text": chunk.text,
            "source": source,
            "conversation_id": conversation_id,
        }

        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=dense,
                payload=payload,
            )
        )

    if points:
        _ensure_collection(client, len(points[0].vector))
        # Upsert in batches of 100
        batch_size = 100
        for i in range(0, len(points), batch_size):
            client.upsert(
                collection_name=settings.qdrant_collection,
                points=points[i : i + batch_size],
            )

    logger.info("Upserted %d points for file_id=%s", len(points), file_id)
    return len(points)
