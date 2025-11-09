from __future__ import annotations

import asyncio
import os
from functools import lru_cache
from typing import List, Dict

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


EMBEDDING_MODEL_DEFAULT = "text-embedding-3-large"


class EmbeddingClient:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is required")
        self.client = AsyncOpenAI(api_key=key)
        self.model = model or os.getenv("EMBEDDING_MODEL", EMBEDDING_MODEL_DEFAULT)
        # per-request memoization map to avoid duplicate embeddings within one run
        self._memo: Dict[str, List[float]] = {}

    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        # self-contained to allow future replacement with reasoning-based similarity
        if len(a) != len(b):
            raise ValueError("Embedding vectors must be of same length")
        dot = 0.0
        na = 0.0
        nb = 0.0
        for ai, bi in zip(a, b):
            dot += ai * bi
            na += ai * ai
            nb += bi * bi
        if na == 0.0 or nb == 0.0:
            return 0.0
        return max(0.0, min(1.0, dot / ((na ** 0.5) * (nb ** 0.5))))

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type(Exception),
    )
    async def get_embedding(self, text: str) -> List[float]:
        cached = self._memo.get(text)
        if cached is not None:
            return cached
        # ensure bounded length input
        cleaned = " ".join(text.strip().split())
        resp = await self.client.embeddings.create(
            model=self.model,
            input=cleaned,
        )
        vec = list(resp.data[0].embedding)
        self._memo[text] = vec
        return vec


