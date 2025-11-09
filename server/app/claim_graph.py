from __future__ import annotations

import asyncio
import uuid
from typing import List, Callable, Awaitable, Dict, Tuple

from .derivatives import DerivativesClient
from .verification import VerificationAgent
from .kalshi_client import KalshiClient
from .embeddings import EmbeddingClient
from .models import (
    ClaimNode,
    ClaimEdge,
    ClaimSource,
    KalshiMarket,
)


class ClaimGraphBuilder:
    """
    Builds a claim graph with streaming SSE updates.
    
    Pipeline:
    1. Create root claim from worldview
    2. Generate 3-5 sets of derivative claims (6-15 per set, self-consistency)
    3. Verify each claim with Exa search
    4. Attach Kalshi markets as sources
    5. Merge and dedupe by confidence
    6. Build edges between claims
    """
    
    def __init__(
        self,
        emit_callback: Callable[[str, dict], Awaitable[None]],
        derivatives_client: DerivativesClient,
        verification_agent: VerificationAgent,
        kalshi_client: KalshiClient,
        embedding_client: EmbeddingClient,
    ):
        self.emit = emit_callback
        self.derivatives_client = derivatives_client
        self.verification_agent = verification_agent
        self.kalshi_client = kalshi_client
        self.embedding_client = embedding_client
        
        self.nodes: List[ClaimNode] = []
        self.edges: List[ClaimEdge] = []
        self.node_map: Dict[str, ClaimNode] = {}
    
    async def build_from_worldview(
        self,
        worldview: str,
        k: int = 200,
        num_derivative_sets: int = 4,
        max_claims: int = 40,
        threshold: float = 0.75,
    ) -> Tuple[List[ClaimNode], List[ClaimEdge], str]:
        """
        Build the complete claim graph.
        
        Args:
            worldview: The core belief
            k: Number of Kalshi results per claim search
            num_derivative_sets: Number of derivative sets to generate (3-5)
            max_claims: Maximum number of claims to keep after merging
            threshold: Similarity threshold for edges
            
        Returns:
            (nodes, edges, core_id)
        """
        # Step 1: Create root claim
        root_id = await self._add_root_claim(worldview)
        
        # Step 2: Generate derivative claims (multiple sets for self-consistency)
        derivative_sets = await self._generate_derivative_sets(
            worldview, num_derivative_sets
        )
        
        # Flatten all derivatives
        all_derivatives = []
        for derivative_set in derivative_sets:
            all_derivatives.extend(derivative_set)
        
        # Step 3: Create claim nodes (status: "generated")
        derivative_nodes = await self._create_derivative_nodes(
            worldview, all_derivatives, root_id
        )
        
        # Step 4: Verify claims in parallel (max 8 concurrent)
        await self._verify_claims_parallel(derivative_nodes, max_concurrent=8)
        
        # Step 5: Merge and dedupe by confidence, keep top N
        merged_nodes = self._merge_and_dedupe(derivative_nodes, max_claims)
        
        # Step 6: Attach Kalshi markets as sources
        await self._attach_market_sources(merged_nodes, k)
        
        # Step 7: Build edges between claims
        await self._build_claim_edges(merged_nodes, threshold)
        
        # Final: Add root to nodes
        self.nodes = [self.node_map[root_id]] + merged_nodes
        
        return self.nodes, self.edges, root_id
    
    async def _add_root_claim(self, worldview: str) -> str:
        """Create and emit the root claim node."""
        root_id = f"claim-{uuid.uuid4().hex[:12]}"
        root_node = ClaimNode(
            id=root_id,
            label=worldview,
            status="verified",  # Root is assumed true
            sources=[],
            similarity=1.0,
            hop=0,
        )
        
        self.node_map[root_id] = root_node
        
        await self.emit("claim_generated", {
            "node": root_node.model_dump(mode="json"),
        })
        
        return root_id
    
    async def _generate_derivative_sets(
        self, worldview: str, num_sets: int
    ) -> List[List[str]]:
        """Generate multiple sets of derivatives for self-consistency."""
        derivative_sets = await self.derivatives_client.generate_multiple_sets(
            worldview, num_sets=num_sets
        )
        return derivative_sets
    
    async def _create_derivative_nodes(
        self, worldview: str, derivatives: List[str], root_id: str
    ) -> List[ClaimNode]:
        """Create claim nodes from derivative strings and emit events."""
        # Get worldview embedding
        worldview_vec = await self.embedding_client.get_embedding(worldview)
        
        # Embed all derivatives in parallel
        async def embed_claim(claim: str) -> Tuple[str, List[float]]:
            vec = await self.embedding_client.get_embedding(claim)
            return claim, vec
        
        tasks = [embed_claim(d) for d in derivatives]
        embedded = await asyncio.gather(*tasks)
        
        # Create nodes
        nodes: List[ClaimNode] = []
        for claim, claim_vec in embedded:
            node_id = f"claim-{uuid.uuid4().hex[:12]}"
            
            # Calculate similarity to root
            similarity = EmbeddingClient.cosine_similarity(worldview_vec, claim_vec)
            
            node = ClaimNode(
                id=node_id,
                label=claim,
                status="generated",
                sources=[],
                similarity=similarity,
                hop=1,  # All derivatives are hop 1 from root
            )
            
            nodes.append(node)
            self.node_map[node_id] = node
            
            # Emit event
            await self.emit("claim_generated", {
                "node": node.model_dump(mode="json"),
            })
            
            # Add edge from root to this claim
            edge = ClaimEdge(
                source=root_id,
                target=node_id,
                type="derives_from",
                weight=similarity,
            )
            self.edges.append(edge)
        
        return nodes
    
    async def _verify_claims_parallel(
        self, nodes: List[ClaimNode], max_concurrent: int = 8
    ):
        """Verify all claims in parallel with concurrency limit."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def verify_one(node: ClaimNode):
            async with semaphore:
                # Update status to verifying
                node.status = "verifying"
                await self.emit("claim_verifying", {
                    "nodeId": node.id,
                    "label": node.label,
                })
                
                try:
                    # Run verification
                    verification = await self.verification_agent.verify_claim(node.label)
                    
                    # Add verification as a source
                    source = ClaimSource(
                        verification=verification,
                        kalshi_market=None,
                    )
                    node.sources.append(source)
                    node.status = "verified"
                    
                    # Update node in map
                    self.node_map[node.id] = node
                    
                    # Emit verified event
                    await self.emit("claim_verified", {
                        "nodeId": node.id,
                        "verification": verification.model_dump(mode="json"),
                    })
                except Exception as e:
                    node.status = "failed"
                    print(f"Verification failed for {node.id}: {e}")
                    await self.emit("claim_verified", {
                        "nodeId": node.id,
                        "error": str(e),
                    })
        
        await asyncio.gather(*[verify_one(node) for node in nodes])
    
    def _merge_and_dedupe(
        self, nodes: List[ClaimNode], max_claims: int
    ) -> List[ClaimNode]:
        """
        Merge similar claims and keep top N by confidence.
        
        For now, simple deduplication by exact text match (case-insensitive).
        Sort by verification confidence and keep top max_claims.
        """
        # Dedupe by lowercase label
        seen = set()
        unique_nodes = []
        for node in nodes:
            key = node.label.lower()
            if key not in seen:
                seen.add(key)
                unique_nodes.append(node)
        
        # Sort by confidence (from verification) descending
        def get_confidence(node: ClaimNode) -> float:
            if node.sources and node.sources[0].verification:
                return node.sources[0].verification.confidence
            return 0.0
        
        unique_nodes.sort(key=get_confidence, reverse=True)
        
        # Keep top N
        return unique_nodes[:max_claims]
    
    async def _attach_market_sources(self, nodes: List[ClaimNode], k: int):
        """Search Kalshi for each claim and attach markets as sources."""
        semaphore = asyncio.Semaphore(8)
        
        async def search_markets(node: ClaimNode):
            async with semaphore:
                try:
                    # Search Kalshi
                    candidates = await self.kalshi_client.search(node.label, limit=3)
                    
                    if not candidates:
                        return
                    
                    # Take top result and add as source
                    top_candidate = candidates[0]
                    market = KalshiMarket(
                        id=top_candidate.id,
                        title=top_candidate.title,
                        url=str(top_candidate.url) if top_candidate.url else "",
                        relevance=0.8,  # Could compute similarity
                    )
                    
                    # Add market as a new source or update existing
                    source = ClaimSource(
                        verification=node.sources[0].verification if node.sources else None,
                        kalshi_market=market,
                    )
                    
                    # Replace sources with updated one
                    if node.sources:
                        node.sources[0] = source
                    else:
                        node.sources.append(source)
                    
                    # Emit event
                    await self.emit("sources_found", {
                        "nodeId": node.id,
                        "market": market.model_dump(mode="json"),
                    })
                except Exception as e:
                    print(f"Market search failed for {node.id}: {e}")
        
        await asyncio.gather(*[search_markets(node) for node in nodes])
    
    async def _build_claim_edges(self, nodes: List[ClaimNode], threshold: float):
        """Build similarity edges between claims."""
        # Get embeddings for all nodes
        node_to_vec: Dict[str, List[float]] = {}
        
        for node in nodes:
            vec = await self.embedding_client.get_embedding(node.label)
            node_to_vec[node.id] = vec
        
        # Compute pairwise similarities
        node_list = list(nodes)
        for i in range(len(node_list)):
            for j in range(i + 1, len(node_list)):
                node_i = node_list[i]
                node_j = node_list[j]
                
                vec_i = node_to_vec[node_i.id]
                vec_j = node_to_vec[node_j.id]
                
                similarity = EmbeddingClient.cosine_similarity(vec_i, vec_j)
                
                if similarity >= threshold:
                    edge = ClaimEdge(
                        source=node_i.id,
                        target=node_j.id,
                        type="similar_to",
                        weight=similarity,
                    )
                    self.edges.append(edge)

