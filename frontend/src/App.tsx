import { useState, useEffect, useCallback, useRef } from "react";
import { Search, Network, Loader2 } from "lucide-react";
import GraphView from "./components/GraphView";
import ChatPanel from "./components/ChatPanel";
import NodeDetail from "./components/NodeDetail";
import { getGraph, getNodeDetail, expandNode, searchNodes } from "./api";
import type { GraphData, GraphNode, NodeDetail as NodeDetailType } from "./types";
import { NODE_COLORS, NODE_TYPE_LABELS } from "./types";

function App() {
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], edges: [] });
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState<NodeDetailType | null>(null);
  const [highlightNodes, setHighlightNodes] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<GraphNode[]>([]);
  const [showSearch, setShowSearch] = useState(false);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const graphContainerRef = useRef<HTMLDivElement>(null);

  // Load graph data
  useEffect(() => {
    getGraph(true)
      .then(setGraphData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  // Resize observer for graph container
  useEffect(() => {
    const el = graphContainerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setDimensions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Handle node click - expand and show details
  const handleNodeClick = useCallback(async (nodeId: string) => {
    try {
      const detail = await getNodeDetail(nodeId);
      setSelectedNode(detail);

      const expanded = await expandNode(nodeId);
      setGraphData((prev) => {
        const existingIds = new Set(prev.nodes.map((n) => n.id));
        const newNodes = expanded.nodes.filter((n) => !existingIds.has(n.id));
        const existingEdges = new Set(prev.edges.map((e) => `${e.source}-${e.target}`));
        const newEdges = expanded.edges.filter((e) => !existingEdges.has(`${e.source}-${e.target}`));
        return {
          nodes: [...prev.nodes, ...newNodes],
          edges: [...prev.edges, ...newEdges],
        };
      });
    } catch (err) {
      console.error("Error expanding node:", err);
    }
  }, []);

  // Handle referenced nodes from chat
  const handleReferencedNodes = useCallback((nodes: string[]) => {
    setHighlightNodes(new Set(nodes));
    setTimeout(() => setHighlightNodes(new Set()), 5000);
  }, []);

  // Search
  const handleSearch = useCallback(async (query: string) => {
    setSearchQuery(query);
    if (query.length < 2) {
      setSearchResults([]);
      return;
    }
    try {
      const result = await searchNodes(query);
      setSearchResults(result.results);
      setShowSearch(true);
    } catch (err) {
      console.error("Search error:", err);
    }
  }, []);

  const handleSearchSelect = useCallback(
    (nodeId: string) => {
      setShowSearch(false);
      setSearchQuery("");
      setSearchResults([]);
      handleNodeClick(nodeId);
      setHighlightNodes(new Set([nodeId]));
      setTimeout(() => setHighlightNodes(new Set()), 3000);
    },
    [handleNodeClick]
  );

  const nodeTypes = [...new Set(graphData.nodes.map((n) => n.type).filter(Boolean))] as string[];

  return (
    <div className="flex flex-col h-screen">
      {/* Top bar */}
      <header className="bg-slate-800 border-b border-slate-700 px-4 py-2 flex items-center gap-4 shrink-0">
        <div className="flex items-center gap-2">
          <Network size={20} className="text-blue-400" />
          <h1 className="text-sm font-bold text-white">SAP O2C Graph Explorer</h1>
        </div>

        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            onFocus={() => searchResults.length > 0 && setShowSearch(true)}
            placeholder="Search nodes..."
            className="w-full bg-slate-900 border border-slate-700 rounded-md pl-9 pr-3 py-1.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
          />
          {showSearch && searchResults.length > 0 && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-slate-800 border border-slate-700 rounded-md shadow-xl max-h-60 overflow-y-auto z-50">
              {searchResults.map((n) => (
                <button
                  key={n.id}
                  onClick={() => handleSearchSelect(n.id)}
                  className="w-full text-left px-3 py-2 hover:bg-slate-700 flex items-center gap-2 text-sm"
                >
                  <div
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: NODE_COLORS[n.type || ""] || "#6b7280" }}
                  />
                  <span className="text-slate-400 text-xs">{NODE_TYPE_LABELS[n.type || ""] || n.type}</span>
                  <span className="text-white truncate">{n.label || n.id}</span>
                  {n.name && <span className="text-slate-500 text-xs truncate">— {n.name as string}</span>}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Legend */}
        <div className="flex items-center gap-3 text-xs">
          {nodeTypes.slice(0, 6).map((type) => (
            <div key={type} className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: NODE_COLORS[type] || "#6b7280" }} />
              <span className="text-slate-400">{NODE_TYPE_LABELS[type] || type}</span>
            </div>
          ))}
        </div>
      </header>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Graph + Node detail */}
        <div className="flex flex-1 relative">
          <div ref={graphContainerRef} className="flex-1">
            {loading ? (
              <div className="flex items-center justify-center h-full">
                <Loader2 size={32} className="animate-spin text-blue-400" />
                <span className="ml-3 text-slate-400">Loading graph...</span>
              </div>
            ) : (
              <GraphView
                data={graphData}
                highlightNodes={highlightNodes}
                selectedNodeId={selectedNode?.node.id || null}
                onNodeClick={handleNodeClick}
                width={dimensions.width - (selectedNode ? 320 : 0)}
                height={dimensions.height}
              />
            )}
          </div>

          {/* Node detail sidebar */}
          {selectedNode && (
            <NodeDetail
              node={selectedNode.node}
              neighbors={selectedNode.neighbors}
              onNeighborClick={handleNodeClick}
              onClose={() => setSelectedNode(null)}
            />
          )}
        </div>

        {/* Chat panel */}
        <div className="w-96 shrink-0">
          <ChatPanel onReferencedNodes={handleReferencedNodes} />
        </div>
      </div>
    </div>
  );
}

export default App;