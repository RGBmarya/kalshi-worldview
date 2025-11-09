from __future__ import annotations

import json
import os
from typing import List

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


DERIVATIVE_PROMPT = """You are a contrarian-but-rigorous thesis exploder.

Given ONE user belief, produce a diverse set of derivative beliefs that could be true if the core belief is true (or that would become more/less likely if it is).

Cover multiple axes: technology milestones, regulation, macro, capital flows, consumer adoption, supply chain, geopolitics, competitive dynamics, and measurable milestones.

Return 20–40 concise derivative beliefs.

Each belief must be:
- Independent and falsifiable (has a measurable claim or milestone).
- Time-bounded when possible.
- Framed in neutral language (no hype).
- Varied in granularity (firm-level, sector-level, policy-level, macro-level).

Output as a JSON array of strings. No commentary.

The thesis to explore is: \"{WORLDVIEW}\"
"""


class DerivativesClient:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is required")
        self.client = AsyncOpenAI(api_key=key)
        self.model = model or os.getenv("LLM_MODEL", "gpt-4.1-mini")

    def _validate(self, items: List[str]) -> List[str]:
        seen = set()
        results: List[str] = []
        for it in items:
            s = " ".join(it.strip().split())
            if not (12 <= len(s) <= 220):
                continue
            key = s.lower()
            if key in seen:
                continue
            seen.add(key)
            results.append(s)
        if not (20 <= len(results) <= 40):
            raise ValueError("Derivative beliefs must be 20–40 items after validation")
        return results

    def _parse_json_array(self, text: str) -> List[str]:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "derivatives" in parsed and isinstance(parsed["derivatives"], list):
            return [str(x) for x in parsed["derivatives"]]
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
        raise ValueError("Unexpected JSON format for derivatives")

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type(Exception),
    )
    async def generate(self, worldview: str) -> List[str]:
        prompt = DERIVATIVE_PROMPT.replace("{WORLDVIEW}", worldview.strip())
        # Prefer JSON mode; fall back to strict parsing if unsupported
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You ONLY reply with valid JSON. No commentary."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "[]"
        try:
            items = self._parse_json_array(content)
        except Exception:
            # Try raw text parse as array
            items = self._parse_json_array(content)
        return self._validate(items)


