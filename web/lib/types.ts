export type GraphNode = {
  id: string;
  label: string;
  url?: string;
  type: "series" | "market";
  similarity: number;
  hop: number;
  // Loading state and trace info
  status?: "generated" | "verifying" | "verified" | "failed";
  loading?: {
    verifying?: boolean;
    searchingMarkets?: boolean;
  };
  trace?: {
    verification?: {
      confidence?: number;
      rationale?: string;
      queries?: string[];
      exaResults?: Array<{
        title: string;
        url: string;
        snippet: string;
      }>;
    };
    market?: {
      id: string;
      title: string;
      url: string;
      relevance: number;
    };
  };
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
      type: "market" as const,
      similarity: n.similarity,
      hop: n.hop,
      status: n.status,
      trace: {
        verification: n.sources[0]?.verification
          ? {
              confidence: n.sources[0].verification.confidence,
              rationale: n.sources[0].verification.rationale,
              exaResults: n.sources[0].verification.exa_results.map((r) => ({
                title: r.title,
                url: r.url,
                snippet: r.snippet,
              })),
            }
          : undefined,
        market: n.sources[0]?.kalshi_market
          ? {
              id: n.sources[0].kalshi_market.id,
              title: n.sources[0].kalshi_market.title,
              url: n.sources[0].kalshi_market.url,
              relevance: n.sources[0].kalshi_market.relevance,
            }
          : undefined,
      },
    })),
    edges: cg.edges.map((e) => ({
      source: e.source,
      target: e.target,
      weight: e.weight,
    })),
  };
}
