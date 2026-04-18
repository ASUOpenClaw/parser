"""
HTTP client for docling-serve (stable v1 API).

API: POST /v1/convert/source
  Request: {"sources": [{"kind": "file", "base64_string": "...", "filename": "doc.pdf"}],
            "options": {"to_formats": ["md"], "do_ocr": true, "ocr_lang": ["ru", "en"]}}
  Response: {"document": {"md_content": "..."}, "status": "success|partial_success|failure"}

Returns the markdown string for the converted document.
Raises on HTTP error or conversion failure.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

import httpx

from .config import settings

logger = logging.getLogger(__name__)


async def convert_to_markdown(path: Path, mime_type: str) -> str:
    """Send a file to docling-serve, return markdown content."""
    raw = path.read_bytes()
    b64 = base64.b64encode(raw).decode()
    ocr_langs = [lang.strip() for lang in settings.ocr_languages.split(",") if lang.strip()]

    payload = {
        "sources": [
            {
                "kind": "file",
                "base64_string": b64,
                "filename": path.name,
            }
        ],
        "options": {
            "to_formats": ["md"],
            "do_ocr": True,
            "ocr_lang": ocr_langs,
        },
    }

    async with httpx.AsyncClient(timeout=600.0) as client:  # large PDFs can be slow
        resp = await client.post(
            f"{settings.docling_url}/v1/convert/source",
            json=payload,
        )
        if not resp.is_success:
            logger.error("docling 422 body: %s", resp.text)
        resp.raise_for_status()

    data = resp.json()
    status = data.get("status", "success").lower()
    if status == "failure":
        errors = data.get("errors") or []
        raise RuntimeError(
            f"docling-serve conversion failed for {path.name}: {errors}"
        )

    document = data.get("document") or {}
    md = document.get("md_content") or ""
    logger.info("docling converted %s → %d chars markdown (status=%s)", path.name, len(md), status)
    return md
