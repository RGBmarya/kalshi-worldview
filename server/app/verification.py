from __future__ import annotations

import json
import os
from typing import List, Callable, Awaitable, Optional

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .exa_client import ExaClient
from .models import VerificationResult, ExaSource
from .llm_schemas import VerificationResponse
from .logging_config import get_logger

logger = get_logger("verification")


VERIFICATION_SYSTEM_PROMPT = """You are a rigorous fact-checker with access to web search.

Your task is to verify the plausibility of claims using evidence from the internet.

When given a claim:
1. Use the search_exa tool to find relevant evidence
2. You may search multiple times with different queries if needed
3. Evaluate the evidence to determine if the claim is plausible
4. Provide a confidence score (0-1) based on the strength of evidence
5. Write a brief rationale (2-3 sentences) explaining your assessment

Confidence scoring:
- 0.8-1.0: Strong evidence supports the claim
- 0.6-0.8: Moderate evidence, claim is plausible
- 0.4-0.6: Mixed or weak evidence
- 0.2-0.4: Evidence suggests claim is unlikely
- 0.0-0.2: Strong evidence against the claim

Be objective and cite specific sources in your rationale."""


class VerificationAgent:
    def __init__(
        self,
        openai_api_key: str | None = None,
        exa_api_key: str | None = None,
        model: str | None = None,
        emit_callback: Callable[[str, dict], Awaitable[None]] | None = None,
    ):
        oai_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not oai_key:
            raise RuntimeError("OPENAI_API_KEY is required")
        
        self.client = AsyncOpenAI(api_key=oai_key)
        self.model = model or os.getenv("VERIFICATION_MODEL", "gpt-4o")
        self.exa_client = ExaClient(api_key=exa_api_key)
        self.emit = emit_callback  # Optional callback for streaming events
        
    def _exa_search_tool_definition(self) -> dict:
        """Define the Exa search tool for OpenAI function calling."""
        return {
            "type": "function",
            "function": {
                "name": "search_exa",
                "description": "Search the internet using Exa to find relevant articles and information about a topic. Returns articles with titles, URLs, and content snippets.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to find relevant information",
                        },
                        "num_results": {
                            "type": "integer",
                            "description": "Number of results to return (default 5, max 10)",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            },
        }
    
    def _execute_exa_search(self, query: str, num_results: int = 5) -> str:
        """Execute an Exa search and return formatted results as a string."""
        sources = self.exa_client.search_and_contents(query, min(num_results, 10))
        
        if not sources:
            return "No results found."
        
        # Format results for the LLM
        results = []
        for i, source in enumerate(sources, 1):
            results.append(
                f"{i}. {source.title}\n"
                f"   URL: {source.url}\n"
                f"   Snippet: {source.snippet}\n"
            )
        
        return "\n".join(results)
    
    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type(Exception),
    )
    async def verify_claim(
        self,
        claim: str,
        node_id: str | None = None,
        emit_callback: Optional[Callable[[str, dict], Awaitable[None]]] = None,
    ) -> VerificationResult:
        """
        Verify a claim using LLM with Exa search tool calling.
        
        Args:
            claim: The claim to verify
            
        Returns:
            VerificationResult with confidence, rationale, and sources
        """
        logger.info(f"Verifying claim: '{claim[:100]}...'")
        
        messages = [
            {"role": "system", "content": VERIFICATION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Please verify this claim and provide your assessment:\n\n{claim}",
            },
        ]
        
        tools = [self._exa_search_tool_definition()]
        all_sources: List[ExaSource] = []
        max_iterations = 5  # Prevent infinite loops
        
        for iteration in range(max_iterations):
            logger.debug(f"Verification iteration {iteration + 1}/{max_iterations}")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                temperature=0.2,
            )
            
            assistant_message = response.choices[0].message
            
            # Add assistant's response to messages
            messages.append({
                "role": "assistant",
                "content": assistant_message.content,
                "tool_calls": assistant_message.tool_calls if assistant_message.tool_calls else None,
            })
            
            # Check if assistant wants to use tools
            if assistant_message.tool_calls:
                logger.debug(f"Assistant requested {len(assistant_message.tool_calls)} tool call(s)")
                for tool_call in assistant_message.tool_calls:
                    if tool_call.function.name == "search_exa":
                        # Parse arguments
                        args = json.loads(tool_call.function.arguments)
                        query = args.get("query", "")
                        num_results = args.get("num_results", 5)
                        
                        logger.debug(f"Searching: '{query}'")
                        
                        # Emit search query event before executing search
                        if emit_callback and node_id:
                            await emit_callback("verification_query", {
                                "nodeId": node_id,
                                "query": query,
                            })
                        
                        # Execute search and collect sources
                        search_results_text = self._execute_exa_search(query, num_results)
                        sources = self.exa_client.search_and_contents(query, num_results)
                        all_sources.extend(sources)
                        
                        # Emit granular events for each source found
                        if emit_callback and node_id:
                            for source in sources:
                                await emit_callback("verification_source_found", {
                                    "nodeId": node_id,
                                    "source": source.model_dump(mode="json"),
                                })
                        
                        # Add tool result to messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": search_results_text,
                        })
            else:
                # No more tool calls, assistant has finished
                logger.debug("Assistant finished reasoning (no more tool calls)")
                break
        
        # Parse the final response to extract confidence and rationale
        logger.debug("Requesting structured final assessment")
        
        # Ask for structured output using Pydantic model
        structure_messages = messages + [
            {
                "role": "user",
                "content": "Based on your search results and analysis, provide your final verification assessment with confidence score and rationale.",
            }
        ]
        
        final_response = await self.client.beta.chat.completions.parse(
            model=self.model,
            messages=structure_messages,
            response_format=VerificationResponse,
            temperature=0.1,
        )
        
        parsed = final_response.choices[0].message.parsed
        
        if not parsed:
            logger.error("No parsed response from structured output")
            raise ValueError("Failed to parse verification response")
        
        logger.info(f"Verification complete: confidence={parsed.confidence:.2f}")
        
        return VerificationResult(
            confidence=parsed.confidence,
            rationale=parsed.rationale,
            exa_results=all_sources[:10],  # Limit to 10 sources
        )

