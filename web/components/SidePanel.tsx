"use client";

import React from "react";
import { GraphNode, Suggestion } from "../lib/types";

export default function SidePanel({
  node,
  suggestion,
  onClose,
  onExpand,
  isExpanding,
}: {
  node?: GraphNode;
  suggestion?: Suggestion;
  onClose: () => void;
  onExpand?: () => void;
  isExpanding?: boolean;
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
        <button onClick={onClose} className="text-gray-500 hover:text-gray-800">
          ✕
        </button>
      </div>
      <div className="mt-2 text-sm text-gray-600">
        <div>
          Type: <span className="font-mono">{node.type}</span>
        </div>
        <div>
          Hop: <span className="font-mono">{node.hop}</span>
        </div>
        <div>
          Similarity:{" "}
          <span className="font-mono">{node.similarity.toFixed(3)}</span>
        </div>
        {node.status && (
          <div>
            Status:{" "}
            <span className="font-mono capitalize">
              {node.status === "verifying" ? "Verifying..." : node.status}
            </span>
          </div>
        )}
      </div>
      {node.trace && (
        <div className="mt-3 border-t pt-3">
          <h4 className="text-sm font-semibold mb-2">Trace Information</h4>
          {(node.loading?.verifying || node.trace.verification) && (
            <div className="mb-3">
              <div className="text-xs font-semibold text-gray-700 mb-1 flex items-center gap-2">
                Verification
                {node.loading?.verifying && (
                  <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-gray-400 border-t-transparent" />
                )}
              </div>
              {node.trace.verification?.queries && node.trace.verification.queries.length > 0 && (
                <div className="mb-2">
                  <div className="text-xs font-semibold text-gray-600 mb-1">Search Queries:</div>
                  <div className="space-y-1">
                    {node.trace.verification.queries.map((query, idx) => (
                      <div key={idx} className="text-xs text-gray-500 italic pl-2 border-l-2 border-gray-300">
                        "{query}"
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {node.trace.verification?.confidence !== undefined ? (
                <>
                  <div className="text-xs text-gray-600 mb-1">
                    Confidence: {Math.round(node.trace.verification.confidence * 100)}%
                  </div>
                  {node.trace.verification.rationale && (
                    <div className="text-xs text-gray-600">
                      {node.trace.verification.rationale}
                    </div>
                  )}
                </>
              ) : (
                <div className="text-xs text-gray-500 italic">Verifying claim...</div>
              )}
              {node.trace.verification?.exaResults && node.trace.verification.exaResults.length > 0 && (
                <div className="mt-2">
                  <div className="text-xs font-semibold text-gray-700 mb-1">
                    Sources ({node.trace.verification.exaResults.length}):
                  </div>
                  <div className="space-y-1">
                    {node.trace.verification.exaResults.slice(0, 3).map((result, idx) => (
                      <div key={idx} className="text-xs text-gray-600">
                        <a
                          href={result.url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-blue-600 hover:underline"
                        >
                          {result.title}
                        </a>
                        <div className="text-gray-500 mt-0.5">{result.snippet}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          {(node.loading?.searchingMarkets || node.trace.market) && (
            <div>
              <div className="text-xs font-semibold text-gray-700 mb-1 flex items-center gap-2">
                Kalshi Market
                {node.loading?.searchingMarkets && (
                  <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-gray-400 border-t-transparent" />
                )}
              </div>
              {node.trace.market ? (
                <>
                  <div className="text-xs text-gray-600 mb-1">
                    {node.trace.market.title}
                  </div>
                  <a
                    href={node.trace.market.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-blue-600 underline"
                  >
                    Open on Kalshi
                  </a>
                </>
              ) : (
                <div className="text-xs text-gray-500 italic">Searching for markets...</div>
              )}
            </div>
          )}
        </div>
      )}
      {!node.trace && (node.loading?.verifying || node.loading?.searchingMarkets) && (
        <div className="mt-3 border-t pt-3">
          <h4 className="text-sm font-semibold mb-2">Trace Information</h4>
          {node.loading?.verifying && (
            <div className="mb-3">
              <div className="text-xs font-semibold text-gray-700 mb-1 flex items-center gap-2">
                Verification
                <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-gray-400 border-t-transparent" />
              </div>
              <div className="text-xs text-gray-500 italic">Verifying claim...</div>
            </div>
          )}
          {node.loading?.searchingMarkets && (
            <div>
              <div className="text-xs font-semibold text-gray-700 mb-1 flex items-center gap-2">
                Kalshi Market
                <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-gray-400 border-t-transparent" />
              </div>
              <div className="text-xs text-gray-500 italic">Searching for markets...</div>
            </div>
          )}
        </div>
      )}
      {node.url && !node.trace?.market && (
        <div className="mt-3">
          <a
            href={node.url}
            target="_blank"
            rel="noreferrer"
            className="text-blue-600 underline"
          >
            Open on Kalshi
          </a>
        </div>
      )}
      {suggestion && (
        <div className="mt-4">
          <div className={`inline-block px-2 py-1 rounded text-xs ${badge}`}>
            Suggested: {suggestion.action} (
            {Math.round(suggestion.confidence * 100)}%)
          </div>
          <p className="mt-2 text-sm text-gray-700">{suggestion.rationale}</p>
        </div>
      )}
      {onExpand && (
        <div className="mt-6">
          <button
            onClick={onExpand}
            disabled={isExpanding}
            className="w-full inline-flex items-center justify-center rounded-md bg-black text-[#f7f3ea] px-4 py-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isExpanding && (
              <span className="mr-2 inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
            )}
            {isExpanding ? "Expanding..." : "Expand"}
          </button>
        </div>
      )}
    </div>
  );
}
