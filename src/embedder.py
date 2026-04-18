"""
OpenAI-compatible embeddings client (LiteLLM → Ollama → Qwen3-Embedding-0.6B).

Dense embeddings only, 1024-dim by default.

Endpoint: POST {base_url}/embeddings
Request:  {"model": "text-embedding-qwen3", "input": ["text1", ...]}
Response: {"data": [{"embedding": [...], "index": 0}, ...]}
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


class Embedder:
    def __init__(
        self,
        url: str = "http://localhost:4000/v1",
        model: str = "text-embedding-qwen3",
        api_key: str = "sk-local-dev",
    ) -> None:
        self._url = url.rstrip("/")
        self._model = model
        self._api_key = api_key
        logger.info("Embedder configured: %s model=%s", self._url, self._model)

    async def embed(self, text: str) -> list[float]:
        """Embed a single text. Returns dense vector."""
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts. Returns list of dense vectors."""
        payload = {"model": self._model, "input": texts}
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{self._url}/embeddings",
                json=payload,
                headers=headers,
            )
        resp.raise_for_status()
        data = resp.json()["data"]
        data.sort(key=lambda d: d["index"])
        return [d["embedding"] for d in data]

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._url}/health/liveliness")
                return resp.status_code == 200
        except Exception:
            return False
