"use client";
import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { GraphNode, GraphEdge } from "@/lib/api-kg";

const colorMap: Record<string, string> = {
  PERSON: "#10b981",
  ORGANIZATION: "#3b82f6",
  LOCATION: "#f59e0b",
  TECHNOLOGY: "#8b5cf6",
  EVENT: "#ec4899",
  CONCEPT: "#06b6d4",
  DATE: "#6b7280",
  Article: "#64748b",
};

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick?: (node: GraphNode) => void;
}

export default function MiniGraph({ nodes, edges, onNodeClick }: Props) {
  const ref = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    if (!ref.current || nodes.length === 0) return;
    const svg = d3.select(ref.current);
    svg.selectAll("*").remove();

    const width = ref.current.clientWidth || 600;
    const height = 280;

    const sim = d3
      .forceSimulation(nodes as any)
      .force("link", d3.forceLink(edges as any).id((d: any) => d.id).distance(80))
      .force("charge", d3.forceManyBody().strength(-200))
      .force("center", d3.forceCenter(width / 2, height / 2));

    const link = svg.append("g")
      .selectAll("line").data(edges).join("line")
      .attr("stroke", "#94a3b8").attr("stroke-width", 1).attr("stroke-opacity", 0.6);

    const node = svg.append("g")
      .selectAll("g").data(nodes).join("g")
      .style("cursor", "pointer")
      .on("click", (_e, d) => onNodeClick?.(d as GraphNode));

    node.append("circle")
      .attr("r", 14)
      .attr("fill", (d) => colorMap[d.type] || "#64748b")
      .attr("stroke", "#fff").attr("stroke-width", 2);

    node.append("text")
      .text((d) => d.name)
      .attr("x", 0).attr("y", 28)
      .attr("text-anchor", "middle").attr("font-size", 11).attr("fill", "#1e293b");

    node.call(
      d3.drag<any, any>()
        .on("start", (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
        .on("drag", (e, d) => { d.fx = e.x; d.fy = e.y; })
        .on("end", (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }) as any,
    );

    sim.on("tick", () => {
      link
        .attr("x1", (d: any) => d.source.x).attr("y1", (d: any) => d.source.y)
        .attr("x2", (d: any) => d.target.x).attr("y2", (d: any) => d.target.y);
      node.attr("transform", (d: any) => `translate(${d.x},${d.y})`);
    });

    return () => { sim.stop(); };
  }, [nodes, edges, onNodeClick]);

  if (nodes.length === 0) {
    return <div className="text-xs text-slate-400 italic px-2 py-3 text-center">(图谱中暂无相关实体)</div>;
  }
  return <svg ref={ref} className="w-full" style={{ height: 280 }} />;
}
