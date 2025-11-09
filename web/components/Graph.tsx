"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  Panel,
  applyNodeChanges,
} from "@xyflow/react";
import type { Edge, Node, NodeChange } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { GraphResponse, Suggestion } from "../lib/types";
import SidePanel from "./SidePanel";

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
}: {
  graph: GraphResponse["graph"];
  suggestions: Suggestion[];
  onExpand?: (nodeId: string, nodeLabel: string, nodeHop: number) => void;
  isExpanding?: boolean;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const suggestionMap = useMemo(() => {
    const m = new Map<string, Suggestion>();
    for (const s of suggestions) m.set(s.nodeId, s);
    return m;
  }, [suggestions]);

  // Build initial nodes from graph
  const initialNodes: Node[] = useMemo(() => {
    // Lay out nodes in non-overlapping rows grouped by hop.
    const H_GAP = 40; // horizontal gap between nodes
    const V_GAP = 200; // vertical gap between rows
    const MARGIN_X = 40;
    const MARGIN_Y = 40;

    // Collect distinct hops in ascending order
    const hops = Array.from(new Set(graph.nodes.map((n) => n.hop))).sort(
      (a, b) => a - b
    );

    // Compute a deterministic position per node id
    const positions = new Map<
      string,
      { x: number; y: number; width: number }
    >();

    let currentY = MARGIN_Y;
    for (const hop of hops) {
      const group = graph.nodes
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

    return graph.nodes.map((n) => {
      const size = 20 + Math.round(20 * n.similarity);
      const pos = positions.get(n.id) ?? { x: 0, y: 0, width: size * 5 };
      return {
        id: n.id,
        data: { label: n.label },
        position: { x: pos.x, y: pos.y },
        style: {
          backgroundColor: hopColor(n.hop),
          color: "white",
          borderRadius: 6,
          border: "1px solid rgba(0,0,0,0.1)",
          padding: 8,
          width: pos.width,
        },
      };
    });
  }, [graph.nodes]);

  // Keep nodes in state so dragging updates positions
  const [nodes, setNodes] = useState<Node[]>(initialNodes);
  useEffect(() => {
    setNodes(initialNodes);
  }, [initialNodes]);

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((nds) => applyNodeChanges(changes, nds));
  }, []);

  const edges: Edge[] = useMemo(() => {
    return graph.edges.map((e) => ({
      id: `${e.source}-${e.target}`,
      source: e.source,
      target: e.target,
      style: {
        stroke: "rgba(0,0,0,0.3)",
        strokeWidth: 1 + 2 * e.weight,
        opacity: Math.max(0.25, e.weight),
      },
    }));
  }, [graph.edges]);

  const selectedSuggestion = selectedId
    ? suggestionMap.get(selectedId)
    : undefined;
  const selectedNode = selectedId
    ? graph.nodes.find((n) => n.id === selectedId)
    : undefined;

  return (
    <div className="w-full h-full relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onNodeClick={(_, node) => setSelectedId(node.id)}
        fitView
      >
        <Background />
        <Controls />
        <Panel position="top-left">
          <div className="text-xs bg-white/80 backdrop-blur px-2 py-1 rounded">
            Nodes: {graph.nodes.length} • Edges: {graph.edges.length}
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
