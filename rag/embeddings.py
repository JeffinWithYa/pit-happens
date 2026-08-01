from __future__ import annotations

import time
from typing import Sequence

import requests

from rag.config import EMBED_BATCH_SIZE, SPUR_BASE_URL, SPUR_EMBED_MODEL, SPUR_EMBED_TOKEN


class SpurEmbedder:
    def __init__(
        self,
        token: str | None = None,
        model: str = SPUR_EMBED_MODEL,
        base_url: str = SPUR_BASE_URL,
        batch_size: int = EMBED_BATCH_SIZE,
    ) -> None:
        self.token = token or SPUR_EMBED_TOKEN
        if not self.token:
            raise RuntimeError(
                "Missing SPUR_EMBED_TOKEN (or spur_embed_token) in environment /.env"
            )
        self.model = model
        self.url = f"{base_url}/embeddings"
        self.batch_size = batch_size
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
        )

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = list(texts[i : i + self.batch_size])
            out.extend(self._embed_batch(batch))
        return out

    def _embed_batch(self, batch: list[str], retries: int = 4) -> list[list[float]]:
        payload = {"model": self.model, "input": batch}
        last_err: Exception | None = None
        for attempt in range(retries):
            try:
                resp = self.session.post(self.url, json=payload, timeout=120)
                if resp.status_code in {429, 500, 502, 503, 504}:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                resp.raise_for_status()
                data = resp.json()
                items = data.get("data") or []
                # OpenAI-style: each item has index + embedding
                items = sorted(items, key=lambda x: x.get("index", 0))
                vectors = [item["embedding"] for item in items]
                if len(vectors) != len(batch):
                    raise RuntimeError(
                        f"Expected {len(batch)} embeddings, got {len(vectors)}"
                    )
                return vectors
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"Spur embedding failed after retries: {last_err}")
