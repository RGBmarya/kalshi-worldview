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
