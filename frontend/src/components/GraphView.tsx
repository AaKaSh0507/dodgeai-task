import { useRef, useCallback, useEffect, useMemo } from "react";
import ForceGraph2D, {
  type ForceGraphMethods,
} from "react-force-graph-2d";
import type { GraphData } from "../types";
import { NODE_COLORS } from "../types";

interface Props {
  data: GraphData;
  highlightNodes: Set<string>;
  selectedNodeId: string | null;
  onNodeClick: (nodeId: string) => void;
  width: number;
  height: number;
}

interface FGNode {
  id: string;
  type?: string;
  label?: string;
  x?: number;
  y?: number;
  [key: string]: unknown;
}

interface FGLink {
  source: string | FGNode;
  target: string | FGNode;
  relationship: string;
}

export default function GraphView({
  data,
  highlightNodes,
  selectedNodeId,
  onNodeClick,
  width,
  height,
}: Props) {
  const fgRef = useRef<ForceGraphMethods<FGNode, FGLink>>(undefined);

  const graphData = useMemo(() => {
    const nodeMap = new Map<string, boolean>();
    const nodes: FGNode[] = data.nodes.map((n) => {
      nodeMap.set(n.id, true);
      return { ...n };
    });

    const links: FGLink[] = data.edges
      .filter((e) => nodeMap.has(e.source) && nodeMap.has(e.target))
      .map((e) => ({
        source: e.source,
        target: e.target,
        relationship: e.relationship,
      }));

    return { nodes, links };
  }, [data]);

  useEffect(() => {
    // Zoom to fit on initial load
    if (fgRef.current && graphData.nodes.length > 0) {
      setTimeout(() => {
        fgRef.current?.zoomToFit(400, 50);
      }, 500);
    }
  }, [graphData.nodes.length]);

  const paintNode = useCallback(
    (node: FGNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const nodeId = node.id as string;
      const nodeType = (node.type as string) || "default";
      const label = (node.label as string) || nodeId;
      const isHighlighted = highlightNodes.has(nodeId);
      const isSelected = selectedNodeId === nodeId;
      const color = NODE_COLORS[nodeType] || "#6b7280";
      const size = isSelected ? 8 : isHighlighted ? 7 : 5;

      // Glow effect for highlighted nodes
      if (isHighlighted || isSelected) {
        ctx.beginPath();
        ctx.arc(node.x!, node.y!, size + 4, 0, 2 * Math.PI);
        ctx.fillStyle = isSelected
          ? `${color}88`
          : `${color}44`;
        ctx.fill();
      }

      // Node circle
      ctx.beginPath();
      ctx.arc(node.x!, node.y!, size, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = isSelected ? "#ffffff" : isHighlighted ? "#ffffffaa" : "#ffffff33";
      ctx.lineWidth = isSelected ? 2 : 1;
      ctx.stroke();

      // Label
      if (globalScale > 1.5 || isSelected || isHighlighted) {
        const fontSize = Math.max(10 / globalScale, 2);
        ctx.font = `${fontSize}px sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        ctx.fillStyle = "#e2e8f0";
        ctx.fillText(label, node.x!, node.y! + size + 2);
      }
    },
    [highlightNodes, selectedNodeId]
  );

  const paintLink = useCallback(
    (link: FGLink, ctx: CanvasRenderingContext2D) => {
      const source = link.source as FGNode;
      const target = link.target as FGNode;
      if (!source.x || !target.x) return;

      ctx.beginPath();
      ctx.moveTo(source.x, source.y!);
      ctx.lineTo(target.x, target.y!);
      ctx.strokeStyle = "#334155";
      ctx.lineWidth = 0.5;
      ctx.stroke();
    },
    []
  );

  return (
    <ForceGraph2D
      ref={fgRef}
      graphData={graphData}
      width={width}
      height={height}
      backgroundColor="#0f172a"
      nodeCanvasObject={paintNode}
      linkCanvasObject={paintLink}
      onNodeClick={(node) => onNodeClick(node.id as string)}
      nodeLabel={(node) => {
        const n = node as FGNode;
        const type = n.type || "Unknown";
        const label = n.label || n.id;
        const name = n.name ? ` - ${n.name}` : "";
        return `${type}: ${label}${name}`;
      }}
      cooldownTicks={100}
      d3AlphaDecay={0.02}
      d3VelocityDecay={0.3}
    />
  );
}
