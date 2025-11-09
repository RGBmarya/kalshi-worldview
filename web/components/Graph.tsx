"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  Panel,
  applyNodeChanges,
  Handle,
  Position,
} from "@xyflow/react";
import type { Edge, Node, NodeChange } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { GraphEdge, GraphResponse, Suggestion } from "../lib/types";
import SidePanel from "./SidePanel";

// Custom node component with trace info
const TraceNode = ({ data, selected }: { data: any; selected?: boolean }) => {
  return (
    <div className="h-full w-full">
      <Handle type="target" position={Position.Top} />
      <div className="font-semibold text-sm mb-1 break-words">
        {data.label}
      </div>
      {data.trace && (
        <div className="text-xs opacity-80 border-t border-white/20 pt-1 mt-1 break-words">
          {data.trace}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
};

const nodeTypes = {
  traceNode: TraceNode,
};

const hopColor = (hop: number) => {
  switch (hop) {
    case 0:
      return "#ef4444"; // red
    case 1:
      return "#f59e0b"; // amber
    case 2:
      return "#10b981"; // emerald
    default:
      return "#3b82f6"; // blue
  }
};

export default function Graph({
  graph,
  suggestions,
  onExpand,
  isExpanding,
  loadingNodes = [],
  extraEdges = [],
}: {
  graph: GraphResponse["graph"];
  suggestions: Suggestion[];
  onExpand?: (nodeId: string, nodeLabel: string, nodeHop: number) => void;
  isExpanding?: boolean;
  loadingNodes?: GraphResponse["graph"]["nodes"];
  extraEdges?: GraphEdge[];
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const suggestionMap = useMemo(() => {
    const m = new Map<string, Suggestion>();
    for (const s of suggestions) m.set(s.nodeId, s);
    return m;
  }, [suggestions]);

  // Merge graph nodes with loading nodes (loading nodes take precedence if they exist)
  const allNodes = useMemo(() => {
    const nodeMap = new Map<string, GraphResponse["graph"]["nodes"][0]>();
    // Add graph nodes first
    for (const node of graph.nodes) {
      nodeMap.set(node.id, node);
    }
    // Override with loading nodes (they have more up-to-date status)
    for (const node of loadingNodes) {
      nodeMap.set(node.id, node);
    }
    return Array.from(nodeMap.values());
  }, [graph.nodes, loadingNodes]);

  // Count loading nodes
  const loadingCount = useMemo(() => {
    return allNodes.filter(
      (n) => n.status === "generated" || n.status === "verifying"
    ).length;
  }, [allNodes]);

  // Build initial nodes from graph
  const initialNodes: Node[] = useMemo(() => {
    // Lay out nodes in non-overlapping rows grouped by hop.
    const H_GAP = 40; // horizontal gap between nodes
    const V_GAP = 200; // vertical gap between rows
    const MARGIN_X = 40;
    const MARGIN_Y = 40;

    // Collect distinct hops in ascending order
    const hops = Array.from(new Set(allNodes.map((n) => n.hop))).sort(
      (a, b) => a - b
    );

    // Compute a deterministic position per node id
    const positions = new Map<
      string,
      { x: number; y: number; width: number }
    >();

    let currentY = MARGIN_Y;
    for (const hop of hops) {
      const group = allNodes
        .filter((n) => n.hop === hop)
        .sort((a, b) => b.similarity - a.similarity);

      let currentX = MARGIN_X + hop * 10; // slight offset per hop for visual variety
      for (const node of group) {
        const size = 20 + Math.round(20 * node.similarity);
        const width = size * 5;
        positions.set(node.id, { x: currentX, y: currentY, width });
        currentX += width + H_GAP;
      }
      currentY += V_GAP;
    }

    return allNodes.map((n) => {
      const size = 20 + Math.round(20 * n.similarity);
      const pos = positions.get(n.id) ?? { x: 0, y: 0, width: size * 5 };
      
      // Determine if node is loading
      const isLoading = n.status === "generated" || n.status === "verifying";
      const isFailed = n.status === "failed";
      
      // Build trace info for tooltip/label
      const traceParts: string[] = [];
      if (n.status === "verifying" || n.loading?.verifying) {
        traceParts.push("Verifying...");
      } else if (n.trace?.verification?.confidence !== undefined) {
        traceParts.push(`Verified (${Math.round(n.trace.verification.confidence * 100)}%)`);
      }
      if (n.loading?.searchingMarkets) {
        traceParts.push("Searching markets...");
      } else if (n.trace?.market) {
        traceParts.push(`Market: ${n.trace.market.title}`);
      }
      
      const traceText = traceParts.length > 0 ? traceParts.join(" • ") : undefined;
      
      const backgroundColor = isLoading 
        ? "#9ca3af" // gray for loading
        : isFailed
        ? "#ef4444" // red for failed
        : hopColor(n.hop);
      
      return {
        id: n.id,
        type: "traceNode",
        data: { 
          label: n.label,
          trace: traceText,
          status: n.status,
          loading: n.loading,
          backgroundColor,
        },
        position: { x: pos.x, y: pos.y },
        style: {
          backgroundColor,
          color: "white",
          borderRadius: 6,
          border: isLoading 
            ? "2px dashed rgba(255,255,255,0.5)" 
            : "1px solid rgba(0,0,0,0.1)",
          padding: 8,
          width: pos.width,
          opacity: isLoading ? 0.6 : 1.0,
        },
      };
    });
  }, [allNodes]);

  // Keep nodes in state so dragging updates positions
  const [nodes, setNodes] = useState<Node[]>(initialNodes);
  useEffect(() => {
    setNodes(initialNodes);
  }, [initialNodes]);

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((nds) => applyNodeChanges(changes, nds));
  }, []);

  const edges: Edge[] = useMemo(() => {
    const combined = [...graph.edges, ...extraEdges];
    return combined.map((e) => ({
      id: `${e.source}-${e.target}`,
      source: e.source,
      target: e.target,
      style: {
        stroke: "rgba(0,0,0,0.3)",
        strokeWidth: 1 + 2 * e.weight,
        opacity: Math.max(0.25, e.weight),
      },
    }));
  }, [graph.edges, extraEdges]);

  const selectedSuggestion = selectedId
    ? suggestionMap.get(selectedId)
    : undefined;
  const selectedNode = selectedId
    ? allNodes.find((n) => n.id === selectedId)
    : undefined;

  return (
    <div className="w-full h-full relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onNodeClick={(_, node) => setSelectedId(node.id)}
        fitView
      >
        <Background />
        <Controls />
        <Panel position="top-left">
          <div className="text-xs bg-white/80 backdrop-blur px-2 py-1 rounded">
            Nodes: {allNodes.length} • Edges: {graph.edges.length}
            {loadingCount > 0 && (
              <span className="ml-2 text-gray-600">
                • Loading: {loadingCount}
              </span>
            )}
          </div>
        </Panel>
      </ReactFlow>
      <SidePanel
        node={selectedNode}
        suggestion={selectedSuggestion}
        onClose={() => setSelectedId(null)}
        onExpand={
          selectedNode && onExpand
            ? () => {
                onExpand(selectedNode.id, selectedNode.label, selectedNode.hop);
              }
            : undefined
        }
        isExpanding={isExpanding}
      />
    </div>
  );
}
