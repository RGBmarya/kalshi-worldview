from __future__ import annotations

import asyncio
from typing import List, Dict, Tuple

from .embeddings import EmbeddingClient
from .kalshi_client import KalshiClient
from .models import GraphNode, GraphEdge, Candidate


async def build_graph(
    worldview: str,
    k: int,
    max_hops: int,
    threshold: float,
    candidates: List[Candidate],
    embedding_client: EmbeddingClient,
) -> Tuple[List[GraphNode], List[GraphEdge], str]:
    """
    Build graph nodes/edges and assign hop layers.
    - Compute embeddings for worldview and all candidates (title + description if present)
    - Node similarity = cosine(candidate_embed, worldview_embed)
    - Edges between node pairs where cosine(node_i_embed, node_j_embed) >= threshold
    - BFS from core node (argmax similarity) to assign hop distances; filter to <= max_hops
    """
    # Embed worldview
    worldview_vec = await embedding_client.get_embedding(worldview)

    # Build candidate text and embed in parallel
    async def embed_candidate_text(cid: str, title: str, description: str | None) -> Tuple[str, List[float]]:
        text = title if not description else f"{title}. {description}"
        vec = await embedding_client.get_embedding(text)
        return cid, vec

    tasks = [embed_candidate_text(c.id, c.title, c.description) for c in candidates]
    embedded: List[Tuple[str, List[float]]] = await asyncio.gather(*tasks, return_exceptions=False)
    id_to_vec: Dict[str, List[float]] = {cid: vec for cid, vec in embedded}

    # Create nodes with similarity to worldview
    nodes: List[GraphNode] = []
    for c in candidates:
        vec = id_to_vec.get(c.id)
        if vec is None:
            continue
        sim = EmbeddingClient.cosine_similarity(worldview_vec, vec)
        nodes.append(
            GraphNode(
                id=c.id,
                label=c.title,
                url=c.url,
                type=c.type,
                similarity=sim,
                hop=-1,  # temp
            )
        )
    if not nodes:
        raise ValueError("No valid nodes found from Kalshi results")

    # Pick core node (argmax similarity)
    core = max(nodes, key=lambda n: n.similarity)
    core_id = core.id

    # Compute pairwise edges using candidate embeddings
    id_list = [n.id for n in nodes]
    edges: List[GraphEdge] = []
    for i in range(len(id_list)):
        vi = id_to_vec[id_list[i]]
        for j in range(i + 1, len(id_list)):
            vj = id_to_vec[id_list[j]]
            w = EmbeddingClient.cosine_similarity(vi, vj)
            if w >= threshold:
                edges.append(
                    GraphEdge(
                        source=id_list[i],
                        target=id_list[j],
                        weight=w,
                    )
                )

    # Build adjacency for BFS
    adj: Dict[str, List[str]] = {n.id: [] for n in nodes}
    for e in edges:
        adj[e.source].append(e.target)
        adj[e.target].append(e.source)

    # BFS to assign hop counts
    hop_map: Dict[str, int] = {nid: -1 for nid in adj.keys()}
    queue: List[str] = [core_id]
    hop_map[core_id] = 0
    qi = 0
    while qi < len(queue):
        cur = queue[qi]
        qi += 1
        for nxt in adj.get(cur, []):
            if hop_map[nxt] == -1:
                hop_map[nxt] = hop_map[cur] + 1
                queue.append(nxt)

    # Assign and filter by max_hops
    filtered_nodes = []
    node_id_set = set()
    for n in nodes:
        hop = hop_map.get(n.id, -1)
        if hop == -1:
            # unreachable nodes get hop=max_hops+1 and are filtered out
            continue
        if hop <= max_hops:
            node_id_set.add(n.id)
            filtered_nodes.append(n.copy(update={"hop": hop}))

    filtered_edges = [e for e in edges if e.source in node_id_set and e.target in node_id_set]

    return filtered_nodes, filtered_edges, core_id


