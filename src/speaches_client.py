"""
Speaches (Whisper) HTTP client for the Parser service.
Raises plain exceptions (not FastAPI HTTPException) — caller handles retries via NATS nack.
"""

from __future__ import annotations

import httpx

from .config import settings


async def transcribe(
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    language: str | None,
    include_timestamps: bool,
) -> dict:
    response_format = "verbose_json" if include_timestamps else "json"
    form: dict = {"model": settings.speaches_model, "response_format": response_format}
    if language:
        form["language"] = language

    headers = {}
    if settings.speaches_api_key:
        headers["Authorization"] = f"Bearer {settings.speaches_api_key}"

    async with httpx.AsyncClient(timeout=settings.speaches_timeout_s) as client:
        resp = await client.post(
            f"{settings.speaches_url}/v1/audio/transcriptions",
            headers=headers,
            data=form,
            files={"file": (filename, file_bytes, mime_type)},
        )
        resp.raise_for_status()

    data = resp.json()

    if include_timestamps:
        return {
            "text": data.get("text", ""),
            "language": data.get("language"),
            "duration_sec": data.get("duration"),
            "segments": [
                {"start": seg.get("start"), "end": seg.get("end"), "text": seg.get("text", "")}
                for seg in data.get("segments", [])
            ],
        }
    return {
        "text": data.get("text", ""),
        "language": data.get("language"),
        "duration_sec": None,
        "segments": [],
    }
