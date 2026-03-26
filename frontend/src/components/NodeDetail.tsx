import type { GraphNode } from "../types";
import { NODE_COLORS, NODE_TYPE_LABELS } from "../types";

interface Props {
  node: GraphNode;
  neighbors: (GraphNode & { direction: string; relationship: string })[];
  onNeighborClick: (nodeId: string) => void;
  onClose: () => void;
}

const HIDDEN_KEYS = new Set(["id", "type", "label", "x", "y", "vx", "vy", "index", "__indexColor"]);

export default function NodeDetail({ node, neighbors, onNeighborClick, onClose }: Props) {
  const color = NODE_COLORS[node.type || ""] || "#6b7280";
  const typeLabel = NODE_TYPE_LABELS[node.type || ""] || node.type || "Unknown";

  const metadata = Object.entries(node).filter(
    ([k, v]) => !HIDDEN_KEYS.has(k) && v !== null && v !== undefined && v !== ""
  );

  const incoming = neighbors.filter((n) => n.direction === "incoming");
  const outgoing = neighbors.filter((n) => n.direction === "outgoing");

  return (
    <div className="bg-slate-800 border-l border-slate-700 h-full overflow-y-auto p-4 w-80">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
          <span className="text-sm font-medium text-slate-400">{typeLabel}</span>
        </div>
        <button
          onClick={onClose}
          className="text-slate-500 hover:text-slate-300 text-lg leading-none"
        >
          ×
        </button>
      </div>

      <h3 className="text-lg font-semibold text-white mb-4">{node.label || node.id}</h3>

      {/* Metadata */}
      {metadata.length > 0 && (
        <div className="mb-4">
          <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Properties</h4>
          <div className="space-y-1">
            {metadata.map(([key, value]) => (
              <div key={key} className="flex justify-between text-sm">
                <span className="text-slate-400 truncate mr-2">{key}</span>
                <span className="text-slate-200 text-right truncate max-w-[180px]" title={String(value)}>
                  {String(value)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Outgoing relationships */}
      {outgoing.length > 0 && (
        <div className="mb-4">
          <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">
            Outgoing ({outgoing.length})
          </h4>
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {outgoing.map((n, i) => (
              <button
                key={i}
                onClick={() => onNeighborClick(n.id)}
                className="w-full text-left text-sm px-2 py-1 rounded hover:bg-slate-700 flex items-center gap-2"
              >
                <div
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: NODE_COLORS[n.type || ""] || "#6b7280" }}
                />
                <span className="text-slate-400 text-xs shrink-0">{n.relationship}</span>
                <span className="text-slate-200 truncate">{n.label || n.id}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Incoming relationships */}
      {incoming.length > 0 && (
        <div className="mb-4">
          <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">
            Incoming ({incoming.length})
          </h4>
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {incoming.map((n, i) => (
              <button
                key={i}
                onClick={() => onNeighborClick(n.id)}
                className="w-full text-left text-sm px-2 py-1 rounded hover:bg-slate-700 flex items-center gap-2"
              >
                <div
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: NODE_COLORS[n.type || ""] || "#6b7280" }}
                />
                <span className="text-slate-400 text-xs shrink-0">{n.relationship}</span>
                <span className="text-slate-200 truncate">{n.label || n.id}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
