"""
FastStream NATS subscriber for transcription.jobs.

Job: download audio from S3 → call Speaches → publish transcription.results
The REST API subscriber handles all DB operations (File + Transcription records).
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

from faststream.nats import NatsBroker, JStream
from faststream.nats.annotations import NatsMessage
from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy
from pydantic import BaseModel

from .config import settings
from .downloader import download
from . import speaches_client

logger = logging.getLogger(__name__)


class TranscriptionJob(BaseModel):
    job_id: str
    task_id: str
    workspace_id: str
    audio_file_id: str
    s3_key: str
    filename: str
    mime_type: str
    language: str | None = None
    include_timestamps: bool = True
    requested_by: str | None = None


def create_transcription_subscriber(broker: NatsBroker) -> None:

    @broker.subscriber(
        settings.transcription_nats_subject,
        stream=JStream(
            name=settings.transcription_nats_stream,
            subjects=["transcription.*"],
            declare=True,
        ),
        durable=settings.transcription_nats_durable,
        config=ConsumerConfig(
            ack_policy=AckPolicy.EXPLICIT,
            deliver_policy=DeliverPolicy.ALL,
            max_deliver=settings.nats_max_retries,
            ack_wait=settings.transcription_ack_wait_s,
        ),
    )
    async def handle_transcription_job(job: TranscriptionJob, msg: NatsMessage) -> None:
        logger.info(
            "Transcription job: id=%s task=%s file=%s",
            job.job_id, job.task_id, job.audio_file_id,
        )
        started_at = datetime.now(UTC)
        try:
            result = await _process(job)
            elapsed = (datetime.now(UTC) - started_at).total_seconds()
            await broker.publish(
                {
                    "job_id": job.job_id,
                    "task_id": job.task_id,
                    "workspace_id": job.workspace_id,
                    "audio_file_id": job.audio_file_id,
                    "filename": job.filename,
                    "requested_by": job.requested_by,
                    "status": "completed",
                    "result": result,
                    "processing_time_sec": elapsed,
                    "completed_at": datetime.now(UTC).isoformat(),
                },
                "transcription.results",
            )
            await msg.ack()
        except Exception as exc:
            logger.error("Transcription job failed: id=%s error=%s", job.job_id, exc, exc_info=True)
            num_delivered = getattr(msg.raw_message.metadata, "num_delivered", 1)
            if num_delivered >= settings.nats_max_retries:
                await broker.publish(
                    {
                        "job_id": job.job_id,
                        "task_id": job.task_id,
                        "workspace_id": job.workspace_id,
                        "audio_file_id": job.audio_file_id,
                        "status": "failed",
                        "error": str(exc),
                        "completed_at": datetime.now(UTC).isoformat(),
                    },
                    "transcription.results",
                )
                await msg.ack()
            else:
                await msg.nack(delay=settings.nats_retry_delay_s)


async def _process(job: TranscriptionJob) -> dict:
    tmp_path = download(job.s3_key)
    try:
        file_bytes = tmp_path.read_bytes()
        return await speaches_client.transcribe(
            file_bytes=file_bytes,
            filename=job.filename,
            mime_type=job.mime_type,
            language=job.language,
            include_timestamps=job.include_timestamps,
        )
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
