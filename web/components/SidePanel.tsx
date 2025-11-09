"use client";

import React from "react";
import { GraphNode, Suggestion } from "../lib/types";

export default function SidePanel({
	node,
	suggestion,
	onClose
}: {
	node?: GraphNode;
	suggestion?: Suggestion;
	onClose: () => void;
}) {
	if (!node) return null;
	const badge =
		suggestion?.action === "YES"
			? "bg-green-100 text-green-700"
			: suggestion?.action === "NO"
			? "bg-red-100 text-red-700"
			: "bg-gray-100 text-gray-700";
	return (
		<div className="absolute top-0 right-0 w-96 h-full bg-white border-l shadow-lg p-4 overflow-y-auto">
			<div className="flex items-start justify-between">
				<h3 className="font-semibold text-lg">{node.label}</h3>
				<button onClick={onClose} className="text-gray-500 hover:text-gray-800">✕</button>
			</div>
			<div className="mt-2 text-sm text-gray-600">
				<div>Type: <span className="font-mono">{node.type}</span></div>
				<div>Hop: <span className="font-mono">{node.hop}</span></div>
				<div>Similarity: <span className="font-mono">{node.similarity.toFixed(3)}</span></div>
			</div>
			{node.url && (
				<div className="mt-3">
					<a href={node.url} target="_blank" rel="noreferrer" className="text-blue-600 underline">Open on Kalshi</a>
				</div>
			)}
			{suggestion && (
				<div className="mt-4">
					<div className={`inline-block px-2 py-1 rounded text-xs ${badge}`}>
						Suggested: {suggestion.action} ({Math.round(suggestion.confidence * 100)}%)
					</div>
					<p className="mt-2 text-sm text-gray-700">{suggestion.rationale}</p>
				</div>
			)}
		</div>
	);
}


