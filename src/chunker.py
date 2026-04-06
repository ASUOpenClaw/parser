"""
Markdown-based chunker.

Splits by headers (# / ## / ###), then further splits long sections by
paragraph boundaries. Preserves section heading as metadata.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

MAX_CHARS = 1500  # target max chunk size


@dataclass
class Chunk:
    text: str
    chunk_index: int
    section: str | None = None
    page: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def chunk_markdown(text: str, max_chars: int = MAX_CHARS) -> list[Chunk]:
    """Split markdown into chunks by header, then paragraph if needed."""
    if not text.strip():
        return []

    # Split on lines that start a header (keep the header with its section)
    parts = re.split(r"(?=\n#{1,6} )", "\n" + text)

    chunks: list[Chunk] = []
    idx = 0

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Extract the section title from the first header line
        header_match = re.match(r"^(#{1,6})\s+(.+?)$", part, re.MULTILINE)
        section = header_match.group(2).strip() if header_match else None

        if len(part) <= max_chars:
            chunks.append(Chunk(text=part, chunk_index=idx, section=section))
            idx += 1
        else:
            # Split by blank lines (paragraphs)
            paragraphs = [p.strip() for p in re.split(r"\n{2,}", part) if p.strip()]
            current: list[str] = []
            current_len = 0

            for para in paragraphs:
                if current_len + len(para) + 2 > max_chars and current:
                    chunks.append(
                        Chunk(
                            text="\n\n".join(current),
                            chunk_index=idx,
                            section=section,
                        )
                    )
                    idx += 1
                    current = []
                    current_len = 0
                current.append(para)
                current_len += len(para) + 2

            if current:
                chunks.append(
                    Chunk(
                        text="\n\n".join(current),
                        chunk_index=idx,
                        section=section,
                    )
                )
                idx += 1

    return chunks
