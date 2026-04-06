"""
Download a file from S3/Garage to a local temp path.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import boto3  # type: ignore[import]

from .config import settings

logger = logging.getLogger(__name__)

_s3_client = None


def _get_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )
    return _s3_client


def download(s3_key: str) -> Path:
    """Download file from S3, return path to a temp file. Caller must clean up."""
    client = _get_client()
    suffix = Path(s3_key).suffix or ".bin"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.close()
    tmp_path = Path(tmp.name)

    logger.info("Downloading s3://%s/%s → %s", settings.s3_bucket, s3_key, tmp_path)
    client.download_file(settings.s3_bucket, s3_key, str(tmp_path))
    return tmp_path
