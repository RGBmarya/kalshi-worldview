export type GraphNode = {
  id: string;
  label: string;
  url?: string;
  type: "series" | "market";
  similarity: number;
  hop: number;
};

export type GraphEdge = {
  source: string;
  target: string;
  weight: number;
};

export type Suggestion = {
  nodeId: string;
  action: "YES" | "NO" | "SKIP";
  confidence: number;
  rationale: string;
  url: string;
};

export type GraphResponse = {
  graph: {
    nodes: GraphNode[];
    edges: GraphEdge[];
    coreId: string;
  };
  suggestions: Suggestion[];
  debug?: {
    derivatives: string[];
  };
};

// Claim-centric streaming graph (from backend /graph/stream)
export type ClaimNode = {
  id: string;
  label: string;
  status: "generated" | "verifying" | "verified" | "failed";
  sources: any[];
  similarity: number;
  hop: number;
};

export type ClaimEdge = {
  source: string;
  target: string;
  type: "derives_from" | "similar_to";
  weight: number;
};

export type ClaimGraph = {
  nodes: ClaimNode[];
  edges: ClaimEdge[];
  coreId: string;
};

// Convert ClaimGraph -> GraphResponse["graph"] for React Flow view
export function claimGraphToDisplayGraph(
  cg: ClaimGraph
): GraphResponse["graph"] {
  return {
    coreId: cg.coreId,
    nodes: cg.nodes.map((n) => ({
      id: n.id,
      label: n.label,
      // default type for display; Graph component doesn't rely on it
      type: "market",
      similarity: n.similarity,
      hop: n.hop,
    })),
    edges: cg.edges.map((e) => ({
      source: e.source,
      target: e.target,
      weight: e.weight,
    })),
  };
}
