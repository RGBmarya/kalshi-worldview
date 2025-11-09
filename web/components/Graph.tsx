"use client";

import React, { useMemo, useState } from "react";
import ReactFlow, { Background, Controls, Edge, Node, Panel } from "@xyflow/react";
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
	suggestions
}: {
	graph: GraphResponse["graph"];
	suggestions: Suggestion[];
}) {
	const [selectedId, setSelectedId] = useState<string | null>(null);

	const suggestionMap = useMemo(() => {
		const m = new Map<string, Suggestion>();
		for (const s of suggestions) m.set(s.nodeId, s);
		return m;
	}, [suggestions]);

	const nodes: Node[] = useMemo(() => {
		return graph.nodes.map((n) => {
			const size = 20 + Math.round(20 * n.similarity);
			return {
				id: n.id,
				data: { label: n.label },
				position: { x: Math.random() * 600, y: Math.random() * 400 },
				style: {
					backgroundColor: hopColor(n.hop),
					color: "white",
					borderRadius: 6,
					border: "1px solid rgba(0,0,0,0.1)",
					padding: 8,
					width: size * 5,
				},
			};
		});
	}, [graph.nodes]);

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

	const selectedSuggestion = selectedId ? suggestionMap.get(selectedId) : undefined;
	const selectedNode = selectedId ? graph.nodes.find((n) => n.id === selectedId) : undefined;

	return (
		<div className="w-full h-full relative">
			<ReactFlow
				nodes={nodes}
				edges={edges}
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
			/>
		</div>
	);
}


