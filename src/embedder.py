"""
TEI (Text Embeddings Inference) HTTP client.

Returns (dense: list[float], sparse: dict[int, float]) per text.
TEI endpoints used:
  POST /embed          → [[float, ...], ...]
  POST /embed_sparse   → [{"index": [...], "value": [...]}, ...]

Usage:
    embedder = Embedder(url="http://gpu-server:8080")
    dense, sparse = await embedder.embed("hello world")
    batch = await embedder.embed_batch(["text1", "text2"])
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


class Embedder:
    def __init__(self, url: str = "http://localhost:8080") -> None:
        self._url = url.rstrip("/")
        logger.info("TEI embedder configured: %s", self._url)

    async def embed(self, text: str) -> tuple[list[float], dict[int, float]]:
        """Embed a single text. Returns (dense, sparse)."""
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(
        self, texts: list[str]
    ) -> list[tuple[list[float], dict[int, float]]]:
        """Embed a list of texts. Returns list of (dense, sparse) tuples."""
        dense_vecs, sparse_vecs = await _fetch_both(self._url, texts)
        return list(zip(dense_vecs, sparse_vecs))

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._url}/health")
                return resp.status_code == 200
        except Exception:
            return False


async def _fetch_both(
    url: str, texts: list[str]
) -> tuple[list[list[float]], list[dict[int, float]]]:
    payload = {"inputs": texts}
    async with httpx.AsyncClient(timeout=120.0) as client:
        dense_resp, sparse_resp = await _gather(
            client.post(f"{url}/embed", json=payload),
            client.post(f"{url}/embed_sparse", json=payload),
        )

    dense_resp.raise_for_status()
    sparse_resp.raise_for_status()

    dense_vecs: list[list[float]] = dense_resp.json()

    # TEI sparse: [{"index": [...], "value": [...]}, ...]
    sparse_vecs: list[dict[int, float]] = [
        {int(i): float(v) for i, v in zip(item["index"], item["value"])}
        for item in sparse_resp.json()
    ]

    return dense_vecs, sparse_vecs


async def _gather(*coros):
    """Run coroutines concurrently and return results in order."""
    import asyncio
    return await asyncio.gather(*coros)
