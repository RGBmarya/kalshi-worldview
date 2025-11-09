/* eslint-disable @next/next/no-img-element */
"use client";

import { useCallback, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { GraphNode, GraphEdge, GraphResponse } from "../lib/types";

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

  const onSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setLoading(true);
      setError(null);
      setGraph(null);
      setSuggestions([]);
      try {
        const res = await fetch(`${API_BASE}/graph`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ worldview }),
        });
        if (!res.ok) {
          const txt = await res.text();
          throw new Error(txt);
        }
        const data: GraphResponse = await res.json();
        setGraph(data.graph);
        setSuggestions(data.suggestions);
      } catch (err: any) {
        setError(err?.message || "Request failed");
      } finally {
        setLoading(false);
      }
    },
    [worldview]
  );

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b bg-white">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center gap-4">
          <div className="font-semibold">Kalshi Event Graph</div>
          <form onSubmit={onSubmit} className="flex-1 flex gap-2">
            <input
              value={worldview}
              onChange={(e) => setWorldview(e.target.value)}
              placeholder="Enter worldview, e.g., 'AI chips demand will surge in 2025'"
              className="flex-1 border rounded px-3 py-2"
            />
            <button
              type="submit"
              disabled={loading || !worldview.trim()}
              className="px-4 py-2 rounded bg-blue-600 text-white disabled:opacity-50"
            >
              {loading ? "Building..." : "Build Graph"}
            </button>
          </form>
        </div>
      </header>
      <main className="flex-1">
        {error && (
          <div className="max-w-4xl mx-auto p-4 text-red-700">{error}</div>
        )}
        {graph ? (
          <div className="h-[calc(100vh-80px)]">
            <Graph graph={graph} suggestions={suggestions} />
          </div>
        ) : (
          <div className="max-w-3xl mx-auto p-8 text-gray-600">
            Enter a worldview and generate the graph.
          </div>
        )}
      </main>
    </div>
  );
}
