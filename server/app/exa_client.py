from __future__ import annotations

import os
from typing import List

from exa_py import Exa
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .models import ExaSource
from .logging_config import get_logger

logger = get_logger("exa")


class ExaClient:
    def __init__(self, api_key: str | None = None):
        key = api_key or os.getenv("EXA_API_KEY")
        if not key:
            raise RuntimeError("EXA_API_KEY is required")
        self.client = Exa(api_key=key)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type(Exception),
    )
    def search_and_contents(
        self,
        query: str,
        num_results: int = 5,
    ) -> List[ExaSource]:
        """
        Search Exa and retrieve content snippets.
        
        Args:
            query: Search query string
            num_results: Number of results to return (default 5)
            
        Returns:
            List of ExaSource objects with title, url, and snippet
        """
        logger.info(f"🔍 Searching Exa: '{query}' (num_results={num_results})")
        
        try:
            # Use the modern search() API (search_and_contents is deprecated)
            response = self.client.search(
                query,
                num_results=num_results,
                contents={"text": {"maxCharacters": 500}},  # Get up to 500 chars per result
                type="auto",  # Let Exa choose the best search type
            )
            
            logger.debug(f"Exa API returned {len(response.results)} results")
            
            sources: List[ExaSource] = []
            for i, result in enumerate(response.results, 1):
                # Extract text snippet from the result
                snippet = ""
                if hasattr(result, "text") and result.text:
                    snippet = result.text[:500]  # Truncate to 500 chars
                
                sources.append(
                    ExaSource(
                        title=result.title or "Untitled",
                        url=result.url,
                        snippet=snippet,
                    )
                )
                logger.debug(f"  {i}. {result.title[:60]}...")
            
            logger.info(f"✓ Found {len(sources)} sources")
            return sources
        except Exception as e:
            # Log error but don't crash - return empty list
            logger.error(f"Exa search failed for '{query}': {e}")
            return []

