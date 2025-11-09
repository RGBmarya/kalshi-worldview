from __future__ import annotations

import os
from typing import List, Dict, Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .models import Candidate


KALSHI_BASE_URL_DEFAULT = "https://api.elections.kalshi.com"


class KalshiClient:
    def __init__(self, base_url: str | None = None, timeout_seconds: float = 12.0):
        self.base_url = base_url or os.getenv("KALSHI_BASE_URL", KALSHI_BASE_URL_DEFAULT)
        self.timeout = httpx.Timeout(timeout_seconds)
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def aclose(self):
        await self._client.aclose()

    def _candidate_from_series(self, s: Dict[str, Any]) -> Candidate:
        # Try to be resilient to field naming
        sid = str(s.get("id") or s.get("series_id") or s.get("ticker") or s.get("slug"))
        title = str(s.get("title") or s.get("name") or sid)
        description = s.get("description")
        url = s.get("url") or s.get("permalink")
        return Candidate(id=f"series:{sid}", type="series", title=title, description=description, url=url)

    def _candidate_from_market(self, m: Dict[str, Any]) -> Candidate:
        mid = str(m.get("id") or m.get("market_id") or m.get("ticker") or m.get("slug"))
        title = str(m.get("title") or m.get("name") or mid)
        description = m.get("description")
        url = m.get("url") or m.get("permalink")
        return Candidate(id=f"market:{mid}", type="market", title=title, description=description, url=url)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type(Exception),
    )
    async def search(self, query: str, k: int) -> List[Candidate]:
        params = {
            "embedding_search": "true",
            "order_by": "querymatch",
            "query": query,
        }
        url = f"{self.base_url}/v1/search/series"
        resp = await self._client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        results: List[Candidate] = []
        # Expect 'series' list
        for s in data.get("series", [])[:k]:
            try:
                results.append(self._candidate_from_series(s))
            except Exception:
                continue
            # If markets embedded, include top few per series
            markets = s.get("markets") or []
            for m in markets[: min(3, len(markets))]:
                try:
                    results.append(self._candidate_from_market(m))
                except Exception:
                    continue
        # Also consider standalone markets if present
        for m in data.get("markets", [])[:k]:
            try:
                results.append(self._candidate_from_market(m))
            except Exception:
                continue
        # Deduplicate by id
        dedup: Dict[str, Candidate] = {}
        for c in results:
            dedup[c.id] = c
        return list(dedup.values())[:k]


