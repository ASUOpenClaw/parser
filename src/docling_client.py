"""
HTTP client for docling-serve.

API: POST /v1alpha/convert/source
  Request: {"file_sources": [{"base64_string": "...", "filename": "doc.pdf"}],
            "options": {"to_formats": ["md"], "do_ocr": true,
                        "ocr_options": {"lang": ["ru", "en"]}}}
  Response: {"converted_sources": [{"md_content": "...", "status": "SUCCESS"}]}

Returns the markdown string for the first (and only) input file.
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
        "file_sources": [
            {
                "base64_string": b64,
                "filename": path.name,
            }
        ],
        "options": {
            "to_formats": ["md"],
            "do_ocr": True,
            "ocr_options": {"lang": ocr_langs},
        },
    }

    async with httpx.AsyncClient(timeout=600.0) as client:  # large PDFs can be slow
        resp = await client.post(
            f"{settings.docling_url}/v1alpha/convert/source",
            json=payload,
        )
        resp.raise_for_status()

    data = resp.json()
    sources = data.get("converted_sources") or data.get("results") or []
    if not sources:
        raise RuntimeError(f"docling-serve returned no results for {path.name}")

    result = sources[0]
    if result.get("status", "SUCCESS").upper() != "SUCCESS":
        raise RuntimeError(
            f"docling-serve conversion failed for {path.name}: {result.get('error')}"
        )

    md = result.get("md_content") or result.get("markdown") or ""
    logger.info("docling converted %s → %d chars markdown", path.name, len(md))
    return md
