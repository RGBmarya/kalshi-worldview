from __future__ import annotations

import json
import os
from typing import List

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .models import Suggestion, GraphNode


SUGGESTION_INSTRUCTIONS = """You are a careful, neutral financial analyst.
Given a worldview and a market title, classify the directional alignment:
- YES: If the worldview implies the market is more likely to resolve YES
- NO: If the worldview implies the market is less likely to resolve YES
- SKIP: If unclear, ambiguous, or unrelated

Return strict JSON with:
{
  "suggestions": [
    { "nodeId": "<id>", "action": "YES|NO|SKIP", "confidence": <0..1>, "rationale": "<short>", "url": "<url>" }
  ]
}
"""


class SuggestionClient:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is required")
        self.client = AsyncOpenAI(api_key=key)
        self.model = model or os.getenv("LLM_MODEL", "gpt-4.1-mini")

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type(Exception),
    )
    async def classify(self, worldview: str, nodes: List[GraphNode]) -> List[Suggestion]:
        # Build compact payload for LLM
        items = []
        for n in nodes:
            items.append(
                {
                    "nodeId": n.id,
                    "title": n.label,
                    "similarity": n.similarity,
                }
            )
        user_payload = {
            "worldview": worldview,
            "markets": items,
        }
        messages = [
            {"role": "system", "content": SUGGESTION_INSTRUCTIONS},
            {
                "role": "user",
                "content": json.dumps(user_payload),
            },
        ]
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or '{"suggestions":[]}'
        data = json.loads(content)
        raw = data.get("suggestions", [])
        out: List[Suggestion] = []
        # url injection will be handled by caller (we don't have it here)
        for r in raw:
            try:
                out.append(
                    Suggestion(
                        nodeId=str(r["nodeId"]),
                        action=str(r["action"]),
                        confidence=float(r.get("confidence", 0.5)),
                        rationale=str(r.get("rationale", "")).strip()[:500],
                        url="http://localhost/",  # placeholder, caller must fill
                    )
                )
            except Exception:
                continue
        return out


