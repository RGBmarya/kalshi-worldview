"use client";

import { useCallback, useRef, useState } from "react";
import dynamic from "next/dynamic";
import {
  GraphResponse,
  ClaimGraph,
  claimGraphToDisplayGraph,
  GraphEdge,
} from "../lib/types";

const Graph = dynamic(() => import("../components/Graph"), { ssr: false });

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export default function Page() {
  const [worldview, setWorldview] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [graph, setGraph] = useState<GraphResponse["graph"] | null>(null);
  const [suggestions, setSuggestions] = useState<GraphResponse["suggestions"]>(
    []
  );
  const [eventCounts, setEventCounts] = useState<Record<string, number>>({});
  const [isExpanding, setIsExpanding] = useState(false);
  // Track loading nodes by ID
  const [loadingNodes, setLoadingNodes] = useState<Map<string, GraphResponse["graph"]["nodes"][0]>>(new Map());
  // Track ephemeral edges while streaming (e.g., root -> claim, parent -> child)
  const [ephemeralEdges, setEphemeralEdges] = useState<GraphEdge[]>([]);
  // Track current core/root id during initial build
  const coreIdRef = useRef<string>("");

  const onSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setLoading(true);
      setError(null);
      setGraph(null);
      setSuggestions([]);
      setEventCounts({});
      setLoadingNodes(new Map());
      setEphemeralEdges([]);
      coreIdRef.current = "";
      try {
        const res = await fetch(`${API_BASE}/graph/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
          },
          body: JSON.stringify({
            worldview,
            k: 200,
            topN: 15,
            threshold: 0.78,
          }),
        });
        if (!res.ok) {
          const txt = await res.text();
          throw new Error(txt || "Request failed");
        }
        if (!res.body) throw new Error("No stream body");

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let completed = false;

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          let idx: number;
          while ((idx = buffer.indexOf("\n\n")) >= 0) {
            const raw = buffer.slice(0, idx);
            buffer = buffer.slice(idx + 2);

            let eventType = "message";
            let dataLine = "";
            for (const line of raw.split("\n")) {
              if (line.startsWith("event: ")) eventType = line.slice(7).trim();
              else if (line.startsWith("data: "))
                dataLine += line.slice(6).trim();
            }

            if (eventType) {
              setEventCounts((prev) => ({
                ...prev,
                [eventType]: (prev[eventType] || 0) + 1,
              }));
            }

            if (!dataLine) continue;
            try {
              const payload = JSON.parse(dataLine);
              if (eventType === "graph_complete") {
                const cg = payload as ClaimGraph;
                const display = claimGraphToDisplayGraph(cg);
                setGraph(display);
                // Clear ephemeral state once final graph is ready
                setEphemeralEdges([]);
                coreIdRef.current = cg.coreId || coreIdRef.current;
                setLoadingNodes(new Map()); // Clear loading nodes
                completed = true;
                setLoading(false);
                try {
                  await reader.cancel();
                } catch {}
                break;
              } else if (eventType === "claim_generated") {
                // Add new node to loading nodes
                const node = payload.node as ClaimGraph["nodes"][0];
                // Track core/root id for hop 0
                if (node.hop === 0) {
                  coreIdRef.current = node.id;
                }
                setLoadingNodes((prev) => {
                  const next = new Map(prev);
                  const displayNode: GraphResponse["graph"]["nodes"][0] = {
                    id: node.id,
                    label: node.label,
                    type: "market",
                    similarity: node.similarity,
                    hop: node.hop,
                    status: node.status,
                    trace: {},
                  };
                  next.set(node.id, displayNode);
                  return next;
                });
                // Update graph if it exists, otherwise create initial graph
                setGraph((prevGraph) => {
                  if (!prevGraph) {
                    return {
                      nodes: [],
                      edges: [],
                      coreId: node.id,
                    };
                  }
                  return prevGraph;
                });
                // Add ephemeral edge from core -> new derivative (hop 1) for visual feedback
                if (node.hop === 1 && coreIdRef.current) {
                  setEphemeralEdges((prev) => [
                    ...prev,
                    { source: coreIdRef.current, target: node.id, weight: 0.3 },
                  ]);
                }
              } else if (eventType === "claim_verifying") {
                // Update node status to verifying and set loading state
                const nodeId = payload.nodeId as string;
                setLoadingNodes((prev) => {
                  const next = new Map(prev);
                  const node = next.get(nodeId);
                  if (node) {
                    next.set(nodeId, {
                      ...node,
                      status: "verifying",
                      loading: { ...node.loading, verifying: true },
                    });
                  }
                  return next;
                });
              } else if (eventType === "verification_query") {
                // Add search query to verification trace progressively
                const nodeId = payload.nodeId as string;
                const query = payload.query as string;
                setLoadingNodes((prev) => {
                  const next = new Map(prev);
                  const node = next.get(nodeId);
                  if (node) {
                    const existingQueries = node.trace?.verification?.queries || [];
                    next.set(nodeId, {
                      ...node,
                      trace: {
                        ...node.trace,
                        verification: {
                          ...node.trace?.verification,
                          queries: [...existingQueries, query],
                        },
                      },
                    });
                  }
                  return next;
                });
              } else if (eventType === "verification_source_found") {
                // Add individual source to verification trace progressively
                const nodeId = payload.nodeId as string;
                const source = payload.source;
                setLoadingNodes((prev) => {
                  const next = new Map(prev);
                  const node = next.get(nodeId);
                  if (node) {
                    const existingResults = node.trace?.verification?.exaResults || [];
                    next.set(nodeId, {
                      ...node,
                      trace: {
                        ...node.trace,
                        verification: {
                          ...node.trace?.verification,
                          exaResults: [...existingResults, source],
                        },
                      },
                    });
                  }
                  return next;
                });
              } else if (eventType === "claim_verified") {
                // Update node with final verification trace and clear loading state
                const nodeId = payload.nodeId as string;
                const verification = payload.verification;
                setLoadingNodes((prev) => {
                  const next = new Map(prev);
                  const node = next.get(nodeId);
                  if (node) {
                    // Merge final verification with existing sources and queries
                    const existingResults = node.trace?.verification?.exaResults || [];
                    const finalResults = verification?.exa_results || existingResults;
                    const existingQueries = node.trace?.verification?.queries || [];
                    next.set(nodeId, {
                      ...node,
                      status: verification ? "verified" : "failed",
                      loading: { ...node.loading, verifying: false },
                      trace: {
                        ...node.trace,
                        verification: verification
                          ? {
                              confidence: verification.confidence,
                              rationale: verification.rationale,
                              queries: existingQueries,
                              exaResults: finalResults,
                            }
                          : undefined,
                      },
                    });
                  }
                  return next;
                });
              } else if (eventType === "market_searching") {
                // Set loading state for market search
                const nodeId = payload.nodeId as string;
                setLoadingNodes((prev) => {
                  const next = new Map(prev);
                  const node = next.get(nodeId);
                  if (node) {
                    next.set(nodeId, {
                      ...node,
                      loading: { ...node.loading, searchingMarkets: true },
                    });
                  }
                  return next;
                });
              } else if (eventType === "sources_found") {
                // Update node with market trace and clear loading state
                const nodeId = payload.nodeId as string;
                const market = payload.market;
                setLoadingNodes((prev) => {
                  const next = new Map(prev);
                  const node = next.get(nodeId);
                  if (node) {
                    next.set(nodeId, {
                      ...node,
                      loading: { ...node.loading, searchingMarkets: false },
                      trace: {
                        ...node.trace,
                        market: market
                          ? {
                              id: market.id,
                              title: market.title,
                              url: market.url,
                              relevance: market.relevance,
                            }
                          : undefined,
                      },
                    });
                  }
                  return next;
                });
              } else if (eventType === "error") {
                setError(payload?.error || "Stream error");
                setLoading(false);
              }
            } catch {
              // ignore partial JSON
            }
          }

          if (completed) break;
        }
      } catch (err: any) {
        setError(err?.message || "Request failed");
        setLoading(false);
      }
    },
    [worldview]
  );

  const handleExpand = useCallback(
    async (nodeId: string, nodeLabel: string, nodeHop: number) => {
      if (!graph) return;
      
      setIsExpanding(true);
      setError(null);
      setEphemeralEdges([]); // Reset ephemeral edges for this expansion
      setLoadingNodes(new Map()); // Reset loading nodes for expansion
      
      try {
        const res = await fetch(`${API_BASE}/graph/expand`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
          },
          body: JSON.stringify({
            parentId: nodeId,
            worldview: nodeLabel,
            parentHop: nodeHop,
            k: 200,
            topN: 15,
            threshold: 0.78,
          }),
        });
        
        if (!res.ok) {
          const txt = await res.text();
          throw new Error(txt || "Expansion failed");
        }
        if (!res.body) throw new Error("No stream body");

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let completed = false;

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          let idx: number;
          while ((idx = buffer.indexOf("\n\n")) >= 0) {
            const raw = buffer.slice(0, idx);
            buffer = buffer.slice(idx + 2);

            let eventType = "message";
            let dataLine = "";
            for (const line of raw.split("\n")) {
              if (line.startsWith("event: ")) eventType = line.slice(7).trim();
              else if (line.startsWith("data: ")) dataLine += line.slice(6).trim();
            }

            if (!dataLine) continue;
            try {
              const payload = JSON.parse(dataLine);
              if (eventType === "graph_complete") {
                const expansion = payload as ClaimGraph;
                const display = claimGraphToDisplayGraph(expansion);
                
                // Merge new nodes and edges into existing graph
                setGraph((prevGraph) => {
                  if (!prevGraph) return display;
                  
                  // Create a set of existing node IDs to avoid duplicates
                  const existingNodeIds = new Set(prevGraph.nodes.map((n) => n.id));
                  
                  // Filter out nodes that already exist
                  const newNodes = display.nodes.filter(
                    (n) => !existingNodeIds.has(n.id)
                  );
                  
                  // Create a set of existing edge IDs (source-target pairs)
                  const existingEdges = new Set(
                    prevGraph.edges.map((e) => `${e.source}-${e.target}`)
                  );
                  
                  // Filter out edges that already exist
                  const newEdges = display.edges.filter(
                    (e) => !existingEdges.has(`${e.source}-${e.target}`)
                  );
                  
                  return {
                    ...prevGraph,
                    nodes: [...prevGraph.nodes, ...newNodes],
                    edges: [...prevGraph.edges, ...newEdges],
                  };
                });
                
                setEphemeralEdges([]); // Clear ephemeral edges once finalized
                setLoadingNodes(new Map()); // Clear loading nodes
                completed = true;
                setIsExpanding(false);
                try {
                  await reader.cancel();
                } catch {}
                break;
              } else if (eventType === "claim_generated") {
                // Add new node to loading nodes
                const node = payload.node as ClaimGraph["nodes"][0];
                setLoadingNodes((prev) => {
                  const next = new Map(prev);
                  const displayNode: GraphResponse["graph"]["nodes"][0] = {
                    id: node.id,
                    label: node.label,
                    type: "market",
                    similarity: node.similarity,
                    hop: node.hop,
                    status: node.status,
                    trace: {},
                  };
                  next.set(node.id, displayNode);
                  return next;
                });
                // Add ephemeral edge from parent -> new child during expansion
                setEphemeralEdges((prev) => [
                  ...prev,
                  { source: nodeId, target: node.id, weight: 0.3 },
                ]);
              } else if (eventType === "claim_verifying") {
                const nodeId = payload.nodeId as string;
                setLoadingNodes((prev) => {
                  const next = new Map(prev);
                  const node = next.get(nodeId);
                  if (node) {
                    next.set(nodeId, {
                      ...node,
                      status: "verifying",
                      loading: { ...node.loading, verifying: true },
                    });
                  }
                  return next;
                });
              } else if (eventType === "verification_query") {
                const nodeId = payload.nodeId as string;
                const query = payload.query as string;
                setLoadingNodes((prev) => {
                  const next = new Map(prev);
                  const node = next.get(nodeId);
                  if (node) {
                    const existingQueries = node.trace?.verification?.queries || [];
                    next.set(nodeId, {
                      ...node,
                      trace: {
                        ...node.trace,
                        verification: {
                          ...node.trace?.verification,
                          queries: [...existingQueries, query],
                        },
                      },
                    });
                  }
                  return next;
                });
              } else if (eventType === "verification_source_found") {
                const nodeId = payload.nodeId as string;
                const source = payload.source;
                setLoadingNodes((prev) => {
                  const next = new Map(prev);
                  const node = next.get(nodeId);
                  if (node) {
                    const existingResults = node.trace?.verification?.exaResults || [];
                    next.set(nodeId, {
                      ...node,
                      trace: {
                        ...node.trace,
                        verification: {
                          ...node.trace?.verification,
                          exaResults: [...existingResults, source],
                        },
                      },
                    });
                  }
                  return next;
                });
              } else if (eventType === "claim_verified") {
                const nodeId = payload.nodeId as string;
                const verification = payload.verification;
                setLoadingNodes((prev) => {
                  const next = new Map(prev);
                  const node = next.get(nodeId);
                  if (node) {
                    const existingResults = node.trace?.verification?.exaResults || [];
                    const finalResults = verification?.exa_results || existingResults;
                    const existingQueries = node.trace?.verification?.queries || [];
                    next.set(nodeId, {
                      ...node,
                      status: verification ? "verified" : "failed",
                      loading: { ...node.loading, verifying: false },
                      trace: {
                        ...node.trace,
                        verification: verification
                          ? {
                              confidence: verification.confidence,
                              rationale: verification.rationale,
                              queries: existingQueries,
                              exaResults: finalResults,
                            }
                          : undefined,
                      },
                    });
                  }
                  return next;
                });
              } else if (eventType === "market_searching") {
                const nodeId = payload.nodeId as string;
                setLoadingNodes((prev) => {
                  const next = new Map(prev);
                  const node = next.get(nodeId);
                  if (node) {
                    next.set(nodeId, {
                      ...node,
                      loading: { ...node.loading, searchingMarkets: true },
                    });
                  }
                  return next;
                });
              } else if (eventType === "sources_found") {
                const nodeId = payload.nodeId as string;
                const market = payload.market;
                setLoadingNodes((prev) => {
                  const next = new Map(prev);
                  const node = next.get(nodeId);
                  if (node) {
                    next.set(nodeId, {
                      ...node,
                      loading: { ...node.loading, searchingMarkets: false },
                      trace: {
                        ...node.trace,
                        market: market
                          ? {
                              id: market.id,
                              title: market.title,
                              url: market.url,
                              relevance: market.relevance,
                            }
                          : undefined,
                      },
                    });
                  }
                  return next;
                });
              } else if (eventType === "error") {
                setError(payload?.error || "Expansion error");
                setIsExpanding(false);
              }
            } catch {
              // ignore partial JSON
            }
          }

          if (completed) break;
        }
      } catch (err: any) {
        setError(err?.message || "Expansion failed");
        setIsExpanding(false);
      }
    },
    [graph]
  );

  return (
    <div className="min-h-screen w-full">
      {graph || loadingNodes.size > 0 ? (
        <div className="h-screen w-full">
          <Graph
            graph={graph || { nodes: [], edges: [], coreId: "" }}
            suggestions={suggestions}
            onExpand={handleExpand}
            isExpanding={isExpanding}
            loadingNodes={Array.from(loadingNodes.values())}
            extraEdges={ephemeralEdges}
          />
        </div>
      ) : (
        <div className="h-screen w-full flex items-center justify-center px-4">
          <div className="w-full max-w-xl rounded-2xl border border-black/10 bg-white/70 backdrop-blur shadow-lg p-6">
            <h1 className="text-2xl mb-2">Enter your worldview</h1>
            <p className="text-sm text-black/70 mb-4">
              Describe a belief about how the world may unfold. We&apos;ll build
              a graph and link relevant Kalshi markets.
            </p>
            <form onSubmit={onSubmit} className="flex flex-col gap-3">
              <input
                value={worldview}
                onChange={(e) => setWorldview(e.target.value)}
                placeholder="e.g., 'AI will transform healthcare by 2027'"
                className="w-full rounded-md border border-black/20 bg-white/80 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-black"
              />
              <button
                type="submit"
                disabled={loading || !worldview.trim()}
                className="inline-flex items-center justify-center rounded-md bg-black text-[#f7f3ea] px-4 py-2 disabled:opacity-50"
              >
                {loading && (
                  <span className="mr-2 inline-block h-4 w-4 animate-spin rounded-full border-2 border-black/30 border-t-[#f7f3ea]" />
                )}
                {loading ? "Building" : "Build Graph"}
              </button>
            </form>
            {loading && (
              <div className="mt-3 text-xs text-black/70">
                Streaming…{" "}
                {Object.entries(eventCounts)
                  .map(([k, v]) => `${k}: ${v}`)
                  .join("  •  ")}
              </div>
            )}
            {error && <div className="mt-3 text-sm text-red-700">{error}</div>}
          </div>
        </div>
      )}
    </div>
  );
}
