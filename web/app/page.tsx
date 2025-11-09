"use client";

import { useCallback, useState } from "react";
import dynamic from "next/dynamic";
import {
  GraphResponse,
  ClaimGraph,
  claimGraphToDisplayGraph,
} from "../lib/types";

const Graph = dynamic(() => import("../components/Graph"), { ssr: false });

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export default function Page() {
  const [worldview, setWorldview] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [graph, setGraph] = useState<GraphResponse["graph"] | null>(null);
  const [suggestions, setSuggestions] =
    useState<GraphResponse["suggestions"]>([]);
  const [eventCounts, setEventCounts] = useState<Record<string, number>>({});

  const onSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setLoading(true);
      setError(null);
      setGraph(null);
      setSuggestions([]);
      setEventCounts({});
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
              else if (line.startsWith("data: ")) dataLine += line.slice(6).trim();
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
                completed = true;
                setLoading(false);
                try {
                  await reader.cancel();
                } catch {}
                break;
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

  return (
    <div className="min-h-screen w-full">
      {graph ? (
        <div className="h-screen w-full">
          <Graph graph={graph} suggestions={suggestions} />
        </div>
      ) : (
        <div className="h-screen w-full flex items-center justify-center px-4">
          <div className="w-full max-w-xl rounded-2xl border border-black/10 bg-white/70 backdrop-blur shadow-lg p-6">
            <h1 className="text-2xl mb-2">Enter your worldview</h1>
            <p className="text-sm text-black/70 mb-4">
              Describe a belief about how the world may unfold. We&apos;ll
              build a graph and link relevant Kalshi markets.
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
