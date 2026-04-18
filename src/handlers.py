"""
FastStream NATS subscriber for indexing.jobs.

Job types:
  index / reindex — download → docling-serve → chunk → TEI embed → Qdrant upsert → publish result
  delete          — delete Qdrant points for file → publish result
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

from faststream.nats import NatsBroker, JStream
from faststream.nats.annotations import NatsMessage
from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy
from pydantic import BaseModel

from .chunker import chunk_markdown
from .config import settings
from .docling_client import convert_to_markdown
from .downloader import download
from .embedder import Embedder
from . import indexer

logger = logging.getLogger(__name__)

_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder(
            url=settings.embedding_url,
            model=settings.embedding_model,
            api_key=settings.embedding_api_key,
        )
    return _embedder


class IndexingJob(BaseModel):
    job_id: str
    type: str  # index | reindex | delete
    workspace_id: str
    file_id: str
    s3_key: str | None = None
    mime_type: str | None = None
    original_name: str | None = None
    folder_id: str | None = None
    metadata: dict | None = None


def _result_payload(
    job: IndexingJob,
    *,
    status: str,
    indexed_chunks: int = 0,
    error: str | None = None,
) -> dict:
    return {
        "job_id": job.job_id,
        "file_id": job.file_id,
        "workspace_id": job.workspace_id,
        "status": status,
        "indexed_chunks": indexed_chunks,
        "error": error,
        "completed_at": datetime.now(UTC).isoformat(),
    }


def create_subscriber(broker: NatsBroker):
    """Register the indexing.jobs subscriber on the given broker."""

    @broker.subscriber(
        settings.nats_subject,
        stream=JStream(
            name=settings.nats_stream,
            subjects=["indexing.*"],
            declare=True,
        ),
        durable=settings.nats_durable,
        config=ConsumerConfig(
            ack_policy=AckPolicy.EXPLICIT,
            deliver_policy=DeliverPolicy.ALL,
            max_deliver=settings.nats_max_retries,
            ack_wait=settings.nats_ack_wait_s,
        ),
    )
    async def handle_job(job: IndexingJob, msg: NatsMessage) -> None:
        logger.info(
            "Job received: id=%s type=%s file_id=%s",
            job.job_id, job.type, job.file_id,
        )
        try:
            result = await _process(job)
            await broker.publish(result, "indexing.results")
            await msg.ack()
        except Exception as exc:
            logger.error("Job failed: id=%s error=%s", job.job_id, exc, exc_info=True)
            num_delivered = getattr(msg.raw_message.metadata, "num_delivered", 1)
            if num_delivered >= settings.nats_max_retries:
                logger.warning("Max retries reached for job %s, publishing failed", job.job_id)
                await broker.publish(
                    _result_payload(job, status="failed", error=str(exc)),
                    "indexing.results",
                )
                await msg.ack()
            else:
                await msg.nack(delay=settings.nats_retry_delay_s)


async def _process(job: IndexingJob) -> dict:
    if job.type == "delete":
        indexer.delete_file_chunks(job.workspace_id, job.file_id)
        return _result_payload(job, status="completed", indexed_chunks=0)

    if job.type not in ("index", "reindex"):
        raise ValueError(f"Unknown job type: {job.type}")

    if not job.s3_key or not job.mime_type:
        raise ValueError(f"Missing s3_key or mime_type for job {job.job_id}")

    # 1. Download from S3
    tmp_path = download(job.s3_key)
    try:
        # 2. Convert via docling-serve → markdown
        markdown = await convert_to_markdown(tmp_path, job.mime_type)
        if not markdown.strip():
            logger.warning("Empty markdown for job %s", job.job_id)
            return _result_payload(job, status="completed", indexed_chunks=0)

        # 3. Chunk
        chunks = chunk_markdown(markdown)
        if not chunks:
            return _result_payload(job, status="completed", indexed_chunks=0)

        # 4. Embed (dense only, Qwen3-Embedding via LiteLLM → Ollama)
        embedder = get_embedder()
        dense_vecs = await embedder.embed_batch([c.text for c in chunks])

        # 5. If reindex: clear old points first
        if job.type == "reindex":
            indexer.delete_file_chunks(job.workspace_id, job.file_id)

        # 6. Upsert to Qdrant
        source = "file"
        conversation_id = None
        if job.metadata:
            source = job.metadata.get("source", "file")
            conversation_id = job.metadata.get("conversation_id")

        n = indexer.upsert_chunks(
            workspace_id=job.workspace_id,
            file_id=job.file_id,
            file_name=job.original_name or job.file_id,
            folder_id=job.folder_id,
            mime_type=job.mime_type,
            source=source,
            conversation_id=conversation_id,
            chunks=chunks,
            dense_vecs=dense_vecs,
        )

        return _result_payload(job, status="completed", indexed_chunks=n)

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
