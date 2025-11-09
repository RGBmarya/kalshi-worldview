from __future__ import annotations

import asyncio
import json
import os
from typing import List, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .embeddings import EmbeddingClient
from .derivatives import DerivativesClient
from .kalshi_client import KalshiClient
from .graph import build_graph
from .models import GraphRequest, GraphResponse, Candidate, GraphNode, Suggestion, ClaimGraph
from .suggest import SuggestionClient
from .claim_graph import ClaimGraphBuilder
from .verification import VerificationAgent


app = FastAPI(title="Kalshi Event Graph")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/graph", response_model=GraphResponse)
async def graph_endpoint(body: GraphRequest):
    worldview = body.worldview.strip()
    if not worldview:
        raise HTTPException(status_code=400, detail="worldview is required")

    # Instantiate clients
    embedding_client = EmbeddingClient()
    deriv_client = DerivativesClient()
    kalshi_client = KalshiClient()
    suggest_client = SuggestionClient()

    # 1) Generate derivatives
    try:
        derivatives = await deriv_client.generate(worldview)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate derivatives: {e}")

    # 2) For each belief: search Kalshi
    sem = asyncio.Semaphore(8)

    async def search_one(q: str):
        try:
            async with sem:
                return await kalshi_client.search(q, body.k)
        except Exception:
            return []

    search_tasks = [search_one(d) for d in derivatives]
    search_results: List[List[Candidate]] = await asyncio.gather(*search_tasks)
    # flatten and dedupe by id
    cand_map: Dict[str, Candidate] = {}
    for lst in search_results:
        for c in lst:
            cand_map[c.id] = c
    candidates = list(cand_map.values())
    if not candidates:
        raise HTTPException(status_code=502, detail="No Kalshi candidates found for the provided worldview")

    # 3) Build graph
    try:
        nodes, edges, core_id = await build_graph(
            worldview=worldview,
            k=body.k,
            max_hops=body.maxHops,
            threshold=body.threshold,
            candidates=candidates,
            embedding_client=embedding_client,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build graph: {e}")

    # 4) Suggestions for top-N nodes (by similarity, within hop limit)
    nodes_sorted = sorted(nodes, key=lambda n: (n.hop, -n.similarity))
    top_nodes = nodes_sorted[: body.topN]
    try:
        raw_suggestions = await suggest_client.classify(worldview, top_nodes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to classify suggestions: {e}")

    # Attach URLs to suggestions
    id_to_url = {n.id: n.url for n in nodes if n.url}
    suggestions: List[Suggestion] = []
    for s in raw_suggestions:
        url = id_to_url.get(s.nodeId)
        if not url:
            # fall back to no suggestion if we lack url context
            continue
        suggestions.append(
            Suggestion(
                nodeId=s.nodeId,
                action=s.action,
                confidence=s.confidence,
                rationale=s.rationale,
                url=url,
            )
        )

    return GraphResponse(
        graph={"nodes": nodes, "edges": edges, "coreId": core_id},
        suggestions=suggestions,
        debug={"derivatives": derivatives},
    )


@app.post("/graph/stream")
async def graph_stream(body: GraphRequest):
    """
    Streaming SSE endpoint that builds a claim graph incrementally.
    
    Events emitted:
    - claim_generated: New claim added
    - claim_verifying: Claim verification started
    - claim_verified: Claim verification complete
    - sources_found: Market sources attached
    - graph_complete: Final graph ready
    """
    worldview = body.worldview.strip()
    if not worldview:
        raise HTTPException(status_code=400, detail="worldview is required")
    
    async def event_generator():
        # Collect events to stream
        events: List[tuple[str, dict]] = []
        
        async def emit(event_type: str, data: dict):
            """Callback to collect SSE events."""
            events.append((event_type, data))
        
        try:
            # Instantiate clients
            embedding_client = EmbeddingClient()
            derivatives_client = DerivativesClient()
            verification_agent = VerificationAgent()
            kalshi_client = KalshiClient()
            
            # Build claim graph
            builder = ClaimGraphBuilder(
                emit_callback=emit,
                derivatives_client=derivatives_client,
                verification_agent=verification_agent,
                kalshi_client=kalshi_client,
                embedding_client=embedding_client,
            )
            
            nodes, edges, core_id = await builder.build_from_worldview(
                worldview=worldview,
                k=body.k,
                num_derivative_sets=4,
                max_claims=body.topN,
                threshold=body.threshold,
            )
            
            # Stream all collected events
            for event_type, data in events:
                yield f"event: {event_type}\n"
                yield f"data: {json.dumps(data)}\n\n"
            
            # Final event: complete graph
            graph = ClaimGraph(
                nodes=nodes,
                edges=edges,
                coreId=core_id,
            )
            
            yield f"event: graph_complete\n"
            yield f"data: {json.dumps(graph.model_dump(mode='json'))}\n\n"
            
        except Exception as e:
            # Emit error event
            yield f"event: error\n"
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


