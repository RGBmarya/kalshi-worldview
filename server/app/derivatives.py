from __future__ import annotations

import os
from typing import List

from openai import AsyncOpenAI
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .logging_config import get_logger
from .llm_schemas import DerivativeBeliefs

logger = get_logger("derivatives")


DERIVATIVE_PROMPT = """You are a contrarian-but-rigorous thesis exploder.

Given ONE user belief, produce a diverse set of derivative beliefs that could be true if the core belief is true (or that would become more/less likely if it is).

Cover multiple axes: technology milestones, regulation, macro, capital flows, consumer adoption, supply chain, geopolitics, competitive dynamics, and measurable milestones.

Return 10–12 concise derivative beliefs.

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
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")

    def _validate_and_clean(self, items: List[str]) -> List[str]:
        """Validate and clean derivatives (6-15 items, lenient)."""
        logger.debug(f"Validating {len(items)} raw items")
        seen = set()
        results: List[str] = []
        filtered = {"too_short": 0, "too_long": 0, "duplicate": 0}
        
        for it in items:
            s = " ".join(it.strip().split())
            if len(s) < 12:
                filtered["too_short"] += 1
                continue
            if len(s) > 220:
                filtered["too_long"] += 1
                continue
            key = s.lower()
            if key in seen:
                filtered["duplicate"] += 1
                continue
            seen.add(key)
            results.append(s)
        
        logger.debug(f"Validation: {len(results)} valid, filtered: {filtered}")
        
        if len(results) < 6:
            raise ValueError(f"Too few derivative beliefs: got {len(results)}, need at least 6 after validation (filtered: {filtered})")
        if len(results) > 15:
            logger.debug(f"Truncating from {len(results)} to 15 items")
            results = results[:15]
        
        return results

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type(Exception),
    )
    async def generate_single_set(self, worldview: str, temperature: float = 0.5) -> List[str]:
        """Generate a single set of 6-15 derivative beliefs using structured outputs."""
        logger.info(f"Generating derivatives (temp={temperature:.1f}) for: '{worldview[:60]}...'")
        
        prompt = DERIVATIVE_PROMPT.replace("{WORLDVIEW}", worldview.strip())
        
        logger.debug(f"Using model: {self.model} with structured outputs")
        
        # Use structured outputs with Pydantic model
        completion = await self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a thesis exploder that generates derivative beliefs in structured format."
                },
                {"role": "user", "content": prompt},
            ],
            response_format=DerivativeBeliefs,
            temperature=temperature,
        )
        
        # Extract parsed response
        parsed = completion.choices[0].message.parsed
        
        if not parsed:
            logger.error("No parsed response from structured output")
            raise ValueError("Failed to parse structured response")
        
        logger.debug(f"Got {len(parsed.derivatives)} raw derivatives from structured output")
        
        try:
            validated = self._validate_and_clean(parsed.derivatives)
            logger.info(f"✓ Generated {len(validated)} valid derivatives (temp={temperature:.1f})")
            return validated
        except Exception as e:
            logger.error(f"Failed to validate derivatives (temp={temperature:.1f}): {e}")
            raise

    async def generate_multiple_sets(
        self,
        worldview: str,
        num_sets: int = 4,
    ) -> List[List[str]]:
        """
        Generate multiple sets of derivatives for self-consistency.
        
        Args:
            worldview: The core belief to explore
            num_sets: Number of sets to generate (default 4, range 3-5)
            
        Returns:
            List of derivative sets, each containing 6-15 beliefs
        """
        import asyncio
        
        num_sets = max(3, min(5, num_sets))  # Clamp to 3-5
        logger.info(f"Generating {num_sets} derivative sets for self-consistency")
        
        # Use slightly different temperatures for diversity
        temperatures = [0.4, 0.5, 0.6, 0.5, 0.4][:num_sets]
        logger.debug(f"Using temperatures: {temperatures}")
        
        # Generate all sets in parallel
        tasks = [
            self.generate_single_set(worldview, temp)
            for temp in temperatures
        ]
        
        sets = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out any failed generations and log errors
        valid_sets = []
        errors = []
        for i, s in enumerate(sets):
            if isinstance(s, list):
                valid_sets.append(s)
                logger.debug(f"Set {i+1}: ✓ {len(s)} derivatives")
            else:
                # Log the error
                error_msg = str(s) if isinstance(s, Exception) else str(type(s))
                errors.append(f"Set {i+1}: {error_msg}")
                logger.warning(f"Set {i+1}: ✗ {error_msg}")
        
        logger.info(f"Successfully generated {len(valid_sets)}/{num_sets} sets")
        
        if len(valid_sets) < 2:
            error_detail = "; ".join(errors) if errors else "Unknown errors"
            logger.error(f"Insufficient valid sets: {error_detail}")
            raise ValueError(
                f"Failed to generate at least 2 sets of derivatives. "
                f"Got {len(valid_sets)} valid sets out of {num_sets}. "
                f"Errors: {error_detail}"
            )
        
        return valid_sets

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type(Exception),
    )
    async def generate(self, worldview: str) -> List[str]:
        """
        Legacy method for backward compatibility.
        Generates multiple sets and flattens to a single list.
        """
        sets = await self.generate_multiple_sets(worldview, num_sets=3)
        # Flatten and dedupe
        all_items = []
        seen = set()
        for s in sets:
            for item in s:
                key = item.lower()
                if key not in seen:
                    seen.add(key)
                    all_items.append(item)
        return all_items


