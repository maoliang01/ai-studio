"use client";

import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import * as d3 from "d3";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Network,
  Search,
  Play,
  RefreshCw,
  Database,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Eye,
  Filter,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Trash2,
  Upload,
  Star,
  X,
} from "lucide-react";
import { toast } from "sonner";
import EntitySourcePopover from "@/components/kg/EntitySourcePopover";

interface GraphNode {
  id: string;
  label: string;
  type: string;
  data: Record<string, any>;
}

interface GraphEdge {
  source: string;
  target: string;
  type: string;
  data: Record<string, any>;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface Stats {
  articles: number;          // Neo4j 中 Article 数
  articles_in_db?: number;   // SQLite 中 success 文章数
  drift_detected?: boolean;  // 数量不一致
  entities: number;
  article_entity_links: number;
  entity_relations: number;
  entities_by_type?: Record<string, number>;
  entities_by_subtype?: Record<string, number>;
}

interface SyncStatus {
  by_status: {
    pending: number;
    processing: number;
    success: number;
    failed: number;
    skipped: number;
  };
  total_in_db: number;
  total_in_kg: number;
  drift_detected: boolean;
  sync_state: {
    in_progress: boolean;
    active_count: number;
    total_processed: number;
    total_failed: number;
    started_at: string | null;
    last_finished_at: string | null;
  };
}

function KnowledgeGraphPageContent() {
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], edges: [] });
  const [stats, setStats] = useState<Stats | null>(null);
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [health, setHealth] = useState<{ status: string; neo4j: { connected: boolean } } | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [entityTypeFilter, setEntityTypeFilter] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [highlightQuery, setHighlightQuery] = useState<string | null>(null);
  const [highlightedNodeIds, setHighlightedNodeIds] = useState<Set<string>>(new Set());
  const [popoverEntity, setPopoverEntity] = useState<string | null>(null);

  const svgRef = useRef<SVGSVGElement>(null);
  const simulationRef = useRef<any>(null);

  // 获取 URL 参数
  const searchParams = useSearchParams();
  const highlight = searchParams.get("highlight");

  // 加载图谱数据
  const loadGraphData = useCallback(async (limit = 500) => {
    setIsLoading(true);
    try {
      const response = await fetch(`/api/kg/graph?limit=${limit}`);
      const data = await response.json();
      if (data.status === "success") {
        setGraphData(data.data);
      }
    } catch (error) {
      console.error("加载图谱失败:", error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // 加载统计数据
  const loadStats = useCallback(async () => {
    try {
      const response = await fetch("/api/kg/stats");
      const data = await response.json();
      if (data.status === "success") {
        setStats(data.stats);
      }
    } catch (error) {
      console.error("加载统计失败:", error);
    }
  }, []);

  // 加载同步状态(各 kg_status 计数 + 后台任务进度)
  const loadSyncStatus = useCallback(async () => {
    try {
      const response = await fetch("/api/kg/sync-status");
      const data = await response.json();
      if (data.status === "success") {
        setSyncStatus(data);
      }
    } catch (error) {
      console.error("加载同步状态失败:", error);
    }
  }, []);

  // 加载健康状态
  const checkHealth = useCallback(async () => {
    try {
      const response = await fetch("/api/kg/health");
      const data = await response.json();
      setHealth(data);
    } catch (error) {
      console.error("健康检查失败:", error);
      setHealth({ status: "unhealthy", neo4j: { connected: false } });
    }
  }, []);

  // 处理高亮查询 - 根据文章标题查找相关节点
  const handleHighlight = useCallback(async (query: string) => {
    setHighlightQuery(query);
    if (!query || graphData.nodes.length === 0) return;

    // 直接在前端匹配文章标题
    const normalizedQuery = query.toLowerCase();
    const articleNodes = graphData.nodes.filter(
      (n) => n.type === "Article" && n.label.toLowerCase().includes(normalizedQuery)
    );

    if (articleNodes.length > 0) {
      // 找到文章节点后，查找所有关联的实体
      const articleIds = new Set(articleNodes.map((n) => n.id));
      const relatedEdges = graphData.edges.filter(
        (e) => articleIds.has(e.source) || articleIds.has(e.target)
      );
      const relatedNodeIds = new Set<string>();
      relatedEdges.forEach((e) => {
        relatedNodeIds.add(e.source);
        relatedNodeIds.add(e.target);
      });
      setHighlightedNodeIds(relatedNodeIds);
    }
  }, [graphData]);

  // 初始化
  useEffect(() => {
    checkHealth();
    loadStats();
    loadSyncStatus();
    loadGraphData();
  }, [checkHealth, loadStats, loadSyncStatus, loadGraphData]);

  // 同步状态轮询:每 5s 拉一次,后台抽取进度 + stats 同步显示
  // 后台有抽取任务时 → 抽取完毕(in_progress: true → false)自动刷新图谱
  const prevInProgressRef = useRef(false);
  useEffect(() => {
    const id = setInterval(() => {
      loadSyncStatus();
      loadStats();
    }, 5000);
    return () => clearInterval(id);
  }, [loadSyncStatus, loadStats]);

  // 抽取完成时自动刷新图谱(从 in_progress=true → false)
  useEffect(() => {
    if (!syncStatus) return;
    const wasInProgress = prevInProgressRef.current;
    const isInProgress = syncStatus.sync_state.in_progress;
    if (wasInProgress && !isInProgress) {
      loadGraphData();
    }
    prevInProgressRef.current = isInProgress;
  }, [syncStatus, loadGraphData]);

  // 处理 URL 参数中的 highlight
  useEffect(() => {
    if (highlight && graphData.nodes.length > 0) {
      handleHighlight(decodeURIComponent(highlight));
    }
  }, [highlight, graphData.nodes.length, handleHighlight]);

  // 清除高亮
  const clearHighlight = () => {
    setHighlightQuery(null);
    setHighlightedNodeIds(new Set());
  };

  // 搜索实体
  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    try {
      const response = await fetch(
        `/api/kg/search?query=${encodeURIComponent(searchQuery)}&limit=20`
      );
      const data = await response.json();
      if (data.status === "success") {
        setSearchResults(data.entities);
        // 将搜索结果作为高亮(D3 节点 id 与 Neo4j Entity.name 一致)
        const ids = new Set<string>(
          (data.entities as Array<{ name: string }>).map((e) => e.name)
        );
        setHighlightedNodeIds((prev) => {
          const next = new Set<string>(prev);
          ids.forEach((id) => next.add(id));
          return next;
        });
      }
    } catch (error) {
      console.error("搜索失败:", error);
    }
  };

  // 批量处理文章
  const handleBatchProcess = async (limit = 50) => {
    setIsProcessing(true);
    try {
      const response = await fetch(`/api/kg/batch-process?limit=${limit}`, {
        method: "POST",
      });
      const data = await response.json();
      if (data.status === "success") {
        alert(
          `处理完成！成功: ${data.results.success}, 跳过: ${data.results.skipped}, 失败: ${data.results.failed}`
        );
        loadGraphData();
        loadStats();
        loadSyncStatus();
      }
    } catch (error) {
      console.error("批量处理失败:", error);
    } finally {
      setIsProcessing(false);
    }
  };

  // 获取实体详情
  const getEntityDetails = async (entityName: string) => {
    try {
      const response = await fetch(`/api/kg/entity/${encodeURIComponent(entityName)}`);
      const data = await response.json();
      if (data.status === "success") {
        return data.data;
      }
    } catch (error) {
      console.error("获取实体详情失败:", error);
    }
    return null;
  };

  // 节点点击处理
  const handleNodeClick = async (node: GraphNode) => {
    setSelectedNode(node);

    // 实体节点:打开出处弹窗(显示来源文章 + 跳转回 articles 页)
    if (node.type !== "Article") {
      setPopoverEntity(node.label);
      return;
    }

    // Article 节点:获取邻居实体信息
    try {
      const details = await getEntityDetails(node.label);
      if (details) {
        console.log("文章邻居实体:", details);
      }
    } catch (e) {
      console.error("获取文章详情失败:", e);
    }
  };

  // D3.js 可视化渲染
  useEffect(() => {
    if (!svgRef.current || graphData.nodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    // 清空已有内容
    svg.selectAll("*").remove();

    // 创建缩放容器
    const g = svg.append("g");

    // 添加缩放功能
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
      });

    svg.call(zoom);

    // 过滤节点
    let nodes = graphData.nodes;
    let edges = graphData.edges;

    if (entityTypeFilter) {
      nodes = nodes.filter((n) => n.type === entityTypeFilter);
      const nodeIds = new Set(nodes.map((n) => n.id));
      edges = edges.filter(
        (e) => nodeIds.has(e.source) && nodeIds.has(e.target)
      );
    }

    // 节点颜色映射
    // - 顶层用 entity_type 区分(PERSON/TECHNOLOGY 等)
    // - 同一 type 下的不同 subtype 用同色系深浅区分(SCIENTIST 深,ENGINEER 浅)
    const colorMap: Record<string, string> = {
      Article: "#4f46e5",
      Entity: "#10b981",
      PERSON: "#f59e0b",
      ORGANIZATION: "#3b82f6",
      LOCATION: "#8b5cf6",
      TECHNOLOGY: "#ec4899",
      EVENT: "#ef4444",
      CONCEPT: "#06b6d4",
      DATE: "#64748b",
    };

    // subtype 颜色变体(在主色基础上做深浅)
    const subtypeShade = (baseColor: string, idx: number): string => {
      // idx 0 = 主色; 1 = 浅; 2 = 深; 3 = 更浅
      const shades: Record<number, string> = {
        0: baseColor,
        1: baseColor + "cc",
        2: baseColor + "88",
        3: baseColor + "55",
      };
      return shades[idx % 4] || baseColor;
    };

    // 节点填色:有 subtype 时按 subtype 哈希到 shade,无 subtype 用主色
    const subtypeIndex: Record<string, number> = {};
    let subtypeCounter = 0;
    for (const n of nodes) {
      if (n.type !== "Article") {
        const st = (n.data as any)?.subtype;
        if (st && !(st in subtypeIndex)) {
          subtypeIndex[st] = subtypeCounter++ % 4;
        }
      }
    }
    const nodeFill = (d: GraphNode): string => {
      const base = colorMap[d.type] || "#64748b";
      const st = (d.data as any)?.subtype;
      if (st && subtypeIndex[st] !== undefined) {
        return subtypeShade(base, subtypeIndex[st]);
      }
      return base;
    };

    // 力导向模拟
    const simulation = d3.forceSimulation(nodes as any)
      .force("link", d3.forceLink(edges as any).id((d: any) => d.id).distance(100))
      .force("charge", d3.forceManyBody().strength(-300))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide().radius(40));

    simulationRef.current = simulation;

    // 绘制边
    const link = g
      .append("g")
      .selectAll("line")
      .data(edges)
      .enter()
      .append("line")
      .attr("stroke", "#94a3b8")
      .attr("stroke-opacity", 0.6)
      .attr("stroke-width", 1.5);

    // 绘制节点
    const node = g
      .append("g")
      .selectAll("circle")
      .data(nodes)
      .enter()
      .append("circle")
      .attr("r", (d: GraphNode) => d.type === "Article" ? 12 : 8)
      .attr("fill", (d: GraphNode) => nodeFill(d))
      .attr("stroke", "#fff")
      .attr("stroke-width", (d: GraphNode) => highlightedNodeIds.has(d.id) ? 4 : 2)
      .attr("stroke-opacity", (d: GraphNode) => highlightedNodeIds.has(d.id) ? 1 : 0.6)
      .style("cursor", "pointer")
      .style("filter", (d: GraphNode) => highlightedNodeIds.has(d.id) ? "drop-shadow(0 0 8px rgba(79, 70, 229, 0.8))" : "none")
      .on("click", (event, d: GraphNode) => {
        event.stopPropagation();
        handleNodeClick(d);
      });

    // 添加标签(实体节点带 subtype 时,后面括号标注中文)
    const label = g
      .append("g")
      .selectAll("text")
      .data(nodes)
      .enter()
      .append("text")
      .text((d: GraphNode) => {
        const st = (d.data as any)?.subtype;
        if (st && d.type !== "Article") {
          const stLabel = SUBTYPE_LABELS[st] || st;
          return `${d.label.substring(0, 12)}[${stLabel}]`;
        }
        return d.label.substring(0, 20);
      })
      .attr("font-size", 10)
      .attr("fill", "#475569")
      .attr("text-anchor", "middle")
      .attr("dy", 20);

    // 拖拽事件
    const drag = d3.drag<SVGCircleElement, GraphNode>()
      .on("start", (event, d: any) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on("drag", (event, d: any) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on("end", (event, d: any) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });

    node.call(drag as any);

    // 更新位置
    simulation.on("tick", () => {
      link
        .attr("x1", (d: any) => d.source.x)
        .attr("y1", (d: any) => d.source.y)
        .attr("x2", (d: any) => d.target.x)
        .attr("y2", (d: any) => d.target.y);

      node.attr("cx", (d: any) => d.x).attr("cy", (d: any) => d.y);
      label.attr("x", (d: any) => d.x).attr("y", (d: any) => d.y);
    });

    return () => {
      simulation.stop();
    };
  }, [graphData, entityTypeFilter, highlightedNodeIds]);

  // 实体类型中英文映射
  const ENTITY_TYPE_LABELS: Record<string, string> = {
    Article: "文章",
    PERSON: "人物",
    ORGANIZATION: "组织",
    LOCATION: "地点",
    TECHNOLOGY: "技术",
    EVENT: "事件",
    CONCEPT: "概念",
    DATE: "时间",
  };

  const SUBTYPE_LABELS: Record<string, string> = {
    SCIENTIST: "科学家",
    ENGINEER: "工程师",
    ACADEMIC: "学者",
    POLITICIAN: "政治家",
    ENTREPRENEUR: "企业家",
    WRITER: "作家",
    ARTIST: "艺术家",
    HISTORICAL: "历史人物",
    COMPANY: "公司",
    RESEARCH_INST: "研究机构",
    UNIVERSITY: "大学",
    GOVERNMENT: "政府",
    INTERNATIONAL: "国际组织",
    NGO: "NGO",
    CITY: "城市",
    COUNTRY: "国家",
    REGION: "地区",
    BUILDING: "建筑",
    ASTRONOMICAL: "天文",
    NATURAL: "自然",
    AI_MODEL: "AI 模型",
    ALGORITHM: "算法",
    PRODUCT: "产品",
    LANGUAGE: "编程语言",
    FRAMEWORK: "框架",
    TOOL: "工具",
    MATERIAL: "材料",
    BIOTECH: "生物技术",
    ENERGY: "能源",
    DEVICE: "设备",
    DISCOVERY: "发现",
    CONFERENCE: "会议",
    PUBLICATION: "出版物",
    AWARD: "奖项",
    AGREEMENT: "协议",
    DISASTER: "灾害",
    CONFLICT: "冲突",
    THEORY: "理论",
    LAW: "定律",
    METHOD: "方法",
    MODEL: "模型",
    SYSTEM: "系统",
    IDEA: "思想",
    DISCIPLINE: "学科",
    FIELD: "领域",
    YEAR: "年",
    MONTH: "月",
    DAY: "日",
    ERA: "时代",
    PERIOD: "时期",
    OTHER: "其他",
  };

  // 获取唯一实体类型(带中文显示)
  const entityTypes = [...new Set(graphData.nodes.map((n) => n.type))];

  return (
    <div className="flex h-[calc(100vh-4rem)]">
      {/* 左侧边栏 */}
      <div className="w-80 border-r bg-gray-50/50 flex flex-col">
        <div className="p-4 border-b">
          <div className="flex items-center justify-between">
            <h1 className="text-lg font-semibold flex items-center gap-2">
              <Network className="w-5 h-5" />
              知识图谱
            </h1>
            {highlightQuery && (
              <Button size="sm" variant="ghost" onClick={clearHighlight}>
                <X className="w-4 h-4" />
              </Button>
            )}
          </div>
          {highlightQuery && (
            <div className="mt-2 flex items-center gap-2 text-sm text-indigo-600 bg-indigo-50 px-3 py-2 rounded-lg">
              <Star className="w-4 h-4" />
              <span className="truncate">{highlightQuery}</span>
            </div>
          )}
        </div>

        {/* 统计信息 */}
        {stats && (
          <div className="p-4 border-b">
            {/* 一致性同步(对账) */}
            <div className="mb-3 flex items-center gap-2 text-sm">
              <span className="text-gray-500">文档管理</span>
              <span className="font-semibold">{stats.articles_in_db ?? "-"}</span>
              <span className="text-gray-400">/</span>
              <span className="text-gray-500">图谱</span>
              <span className="font-semibold">{stats.articles}</span>
              <span className="text-gray-400">篇</span>
              {stats.drift_detected && (
                <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded">漂移</span>
              )}
              <button
                onClick={async () => {
                  if (!confirm("是否自动修复漂移?点确定将自动补抽缺失文章、删除孤儿。")) return;
                  try {
                    const res = await fetch("/api/kg/reconcile?apply=true", { method: "POST" });
                    const data = await res.json();
                    alert(
                      `对账结果:\n` +
                      `  文档管理: ${data.sqlite_count}\n` +
                      `  图谱: ${data.kg_count}\n` +
                      `  缺失: ${data.missing_in_kg.length}\n` +
                      `  孤儿: ${data.orphan_in_kg.length}\n` +
                      `  脏数据: ${data.dirty_in_kg.length}` +
                      (data.fixed ? `\n已修复: ${JSON.stringify(data.fixed)}` : "")
                    );
                    loadStats();
                    loadGraphData();
                  } catch (e) {
                    alert("对账失败: " + e);
                  }
                }}
                className="ml-auto text-xs bg-indigo-50 text-indigo-700 hover:bg-indigo-100 px-2 py-1 rounded border border-indigo-200"
              >
                对账
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-white p-3 rounded-lg">
                <div className="text-2xl font-bold text-indigo-600">
                  {stats.articles}
                </div>
                <div className="text-xs text-gray-500">文章</div>
              </div>
              <div className="bg-white p-3 rounded-lg">
                <div className="text-2xl font-bold text-emerald-600">
                  {stats.entities}
                </div>
                <div className="text-xs text-gray-500">实体</div>
              </div>
              <div className="bg-white p-3 rounded-lg">
                <div className="text-2xl font-bold text-blue-600">
                  {stats.article_entity_links}
                </div>
                <div className="text-xs text-gray-500">文章-实体</div>
              </div>
              <div className="bg-white p-3 rounded-lg">
                <div className="text-2xl font-bold text-purple-600">
                  {stats.entity_relations}
                </div>
                <div className="text-xs text-gray-500">实体关系</div>
              </div>
            </div>

            {/* 实体按类型细分 */}
            {stats.entities_by_type && Object.keys(stats.entities_by_type).length > 0 && (
              <div className="mt-3">
                <div className="text-[10px] text-gray-500 mb-1">实体类型分布</div>
                <div className="space-y-1">
                  {Object.entries(stats.entities_by_type)
                    .sort(([, a], [, b]) => b - a)
                    .map(([t, c]) => {
                      const pct = stats.entities ? (c / stats.entities) * 100 : 0;
                      const color =
                        t === "PERSON" ? "#f59e0b" :
                        t === "ORGANIZATION" ? "#3b82f6" :
                        t === "LOCATION" ? "#8b5cf6" :
                        t === "TECHNOLOGY" ? "#ec4899" :
                        t === "EVENT" ? "#ef4444" :
                        t === "CONCEPT" ? "#06b6d4" :
                        t === "DATE" ? "#64748b" : "#10b981";
                      const label = ENTITY_TYPE_LABELS[t] || t;
                      return (
                        <div key={t} className="flex items-center gap-2 text-xs">
                          <div className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
                          <span className="text-gray-700 w-20 truncate">{label}</span>
                          <div className="flex-1 h-1.5 bg-gray-100 rounded overflow-hidden">
                            <div className="h-full" style={{ width: `${pct}%`, background: color }} />
                          </div>
                          <span className="text-gray-500 w-8 text-right">{c}</span>
                        </div>
                      );
                    })}
                </div>
              </div>
            )}
          </div>
        )}

        {/* 同步状态面板(各 kg_status 计数 + 后台任务进度) */}
        {syncStatus && (
          <div className="p-4 border-b">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">同步状态</span>
              {syncStatus.sync_state.in_progress ? (
                <span className="flex items-center gap-1 text-xs bg-amber-50 text-amber-700 px-2 py-0.5 rounded border border-amber-200">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  抽取中 ({syncStatus.sync_state.active_count})
                </span>
              ) : (
                <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                  空闲
                </span>
              )}
            </div>
            <div className="grid grid-cols-5 gap-1 text-center text-xs">
              <div className="bg-white p-2 rounded">
                <div className="text-base font-semibold text-emerald-600">
                  {syncStatus.by_status.success}
                </div>
                <div className="text-gray-500">已入图</div>
              </div>
              <div className="bg-white p-2 rounded">
                <div className="text-base font-semibold text-amber-600">
                  {syncStatus.by_status.pending}
                </div>
                <div className="text-gray-500">待抽</div>
              </div>
              <div className="bg-white p-2 rounded">
                <div className="text-base font-semibold text-blue-600">
                  {syncStatus.by_status.processing}
                </div>
                <div className="text-gray-500">抽中</div>
              </div>
              <div className="bg-white p-2 rounded">
                <div className="text-base font-semibold text-red-600">
                  {syncStatus.by_status.failed}
                </div>
                <div className="text-gray-500">失败</div>
              </div>
              <div className="bg-white p-2 rounded">
                <div className="text-base font-semibold text-gray-500">
                  {syncStatus.by_status.skipped}
                </div>
                <div className="text-gray-500">跳过</div>
              </div>
            </div>
            {syncStatus.sync_state.total_processed > 0 && (
              <div className="mt-2 text-[10px] text-gray-500 leading-tight">
                本会话已处理 {syncStatus.sync_state.total_processed} 篇
                {syncStatus.sync_state.total_failed > 0 &&
                  `,失败 ${syncStatus.sync_state.total_failed} 篇`}
                {syncStatus.sync_state.last_finished_at &&
                  ` · 上次完成 ${new Date(syncStatus.sync_state.last_finished_at).toLocaleTimeString("zh-CN")}`}
              </div>
            )}
            {(syncStatus.by_status.pending > 0 || syncStatus.by_status.skipped > 0) && (
              <Button
                size="sm"
                className="w-full mt-2 h-7 text-xs bg-indigo-600 hover:bg-indigo-700"
                disabled={syncStatus.sync_state.in_progress}
                onClick={async () => {
                  if (!confirm(`立即抽取 ${syncStatus.by_status.pending + syncStatus.by_status.skipped} 篇待抽文章?后台并发 3 个任务,每篇 0.5s 间隔。`)) return;
                  try {
                    const res = await fetch("/api/kg/process-pending?limit=200", { method: "POST" });
                    const data = await res.json();
                    if (data.status === "success") {
                      toast.success(`已排入 ${data.scheduled} 个抽取任务(扫描 ${data.scanned} 篇)`);
                      setTimeout(() => loadSyncStatus(), 500);
                    } else {
                      toast.error(data.detail || data.error || "启动失败");
                    }
                  } catch (e) {
                    toast.error("启动失败: " + (e instanceof Error ? e.message : String(e)));
                  }
                }}
              >
                {syncStatus.sync_state.in_progress ? (
                  <><Loader2 className="w-3 h-3 mr-1 animate-spin" />抽取中</>
                ) : (
                  <><Play className="w-3 h-3 mr-1" />立即抽取 ({syncStatus.by_status.pending + syncStatus.by_status.skipped})</>
                )}
              </Button>
            )}
          </div>
        )}

        {/* 搜索 */}
        <div className="p-4 border-b">
          <div className="flex gap-2">
            <Input
              placeholder="搜索实体..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            />
            <Button size="icon" onClick={handleSearch}>
              <Search className="w-4 h-4" />
            </Button>
          </div>

          {searchResults.length > 0 && (
            <div className="mt-3 space-y-2">
              {searchResults.slice(0, 5).map((entity, idx) => (
                <div
                  key={idx}
                  className="bg-white p-2 rounded cursor-pointer hover:bg-gray-100"
                  onClick={() => {
                    setSelectedNode({
                      id: entity.name,
                      label: entity.name,
                      type: entity.entity_type,
                      data: entity,
                    });
                  }}
                >
                  <div className="font-medium text-sm">{entity.name}</div>
                  <Badge variant="secondary" className="text-xs mt-1">
                    {ENTITY_TYPE_LABELS[entity.entity_type] || entity.entity_type}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 筛选 */}
        <div className="p-4 border-b">
          <div className="flex items-center gap-2 mb-2">
            <Filter className="w-4 h-4" />
            <span className="text-sm font-medium">筛选类型</span>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant={entityTypeFilter === null ? "default" : "outline"}
              onClick={() => setEntityTypeFilter(null)}
            >
              全部
            </Button>
            {entityTypes.map((type) => (
              <Button
                key={type}
                size="sm"
                variant={entityTypeFilter === type ? "default" : "outline"}
                onClick={() => setEntityTypeFilter(type)}
              >
                {ENTITY_TYPE_LABELS[type] || type}
              </Button>
            ))}
          </div>
        </div>

        {/* 操作 */}
        <div className="p-4 border-b space-y-2">
          <Button
            className="w-full"
            onClick={() => handleBatchProcess(50)}
            disabled={isProcessing}
          >
            {isProcessing ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                处理中...
              </>
            ) : (
              <>
                <Play className="w-4 h-4 mr-2" />
                批量处理文章
              </>
            )}
          </Button>
          <Button
            variant="outline"
            className="w-full"
            onClick={() => loadGraphData()}
            disabled={isLoading}
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            刷新图谱
          </Button>
        </div>

        {/* 选中节点详情 */}
        {selectedNode && (
          <div className="p-4 flex-1 overflow-auto">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">选中节点</span>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setSelectedNode(null)}
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            </div>
            <Card className="p-3">
              <div className="space-y-2">
                <div>
                  <div className="text-xs text-gray-500">名称</div>
                  <div className="font-medium">{selectedNode.label}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">类型</div>
                  <Badge>{ENTITY_TYPE_LABELS[selectedNode.type] || selectedNode.type}</Badge>
                </div>
                {selectedNode.data?.description && (
                  <div>
                    <div className="text-xs text-gray-500">描述</div>
                    <div className="text-sm text-gray-700">
                      {selectedNode.data.description}
                    </div>
                  </div>
                )}
              </div>
            </Card>
          </div>
        )}

        {/* 状态信息 */}
        <div className="p-4 border-t mt-auto">
          <div className="flex items-center gap-2 text-sm">
            {health?.neo4j?.connected ? (
              <>
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                <span className="text-emerald-600">Neo4j 已连接</span>
              </>
            ) : (
              <>
                <AlertCircle className="w-4 h-4 text-red-500" />
                <span className="text-red-600">Neo4j 未连接</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* 主图谱区域 */}
      <div className="flex-1 flex flex-col bg-gray-100">
        {/* 工具栏 */}
        <div className="h-12 border-b bg-white flex items-center px-4 gap-4">
          <span className="text-sm text-gray-500">
            {graphData.nodes.length} 节点 / {graphData.edges.length} 边
          </span>
          <Separator orientation="vertical" className="h-6" />
          <span className="text-xs text-gray-400">
            拖拽节点可移动 | 滚轮缩放 | 点击节点查看详情
          </span>
        </div>

        {/* 图谱画布 */}
        <div className="flex-1 relative">
          {isLoading ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
            </div>
          ) : graphData.nodes.length === 0 ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-500">
              <Network className="w-16 h-16 mb-4 text-gray-300" />
              <p className="text-lg mb-2">暂无图谱数据</p>
              <p className="text-sm">点击"批量处理文章"开始构建知识图谱</p>
            </div>
          ) : (
            <svg
              ref={svgRef}
              className="w-full h-full"
              style={{ background: "#f8fafc" }}
            />
          )}
        </div>

        {/* 图例 - 包含所有 entity_type 细分领域 */}
        <div className="h-10 border-t bg-white flex items-center px-4 gap-4 overflow-x-auto">
          <span className="text-xs text-gray-500 shrink-0">图例：</span>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1 shrink-0">
              <div className="w-3 h-3 rounded-full bg-indigo-600" />
              <span className="text-xs">文章</span>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <div className="w-3 h-3 rounded-full bg-amber-500" />
              <span className="text-xs">人物</span>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <div className="w-3 h-3 rounded-full bg-blue-500" />
              <span className="text-xs">组织</span>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <div className="w-3 h-3 rounded-full bg-violet-500" />
              <span className="text-xs">地点</span>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <div className="w-3 h-3 rounded-full bg-pink-500" />
              <span className="text-xs">技术</span>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <div className="w-3 h-3 rounded-full bg-red-500" />
              <span className="text-xs">事件</span>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <div className="w-3 h-3 rounded-full bg-cyan-500" />
              <span className="text-xs">概念</span>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <div className="w-3 h-3 rounded-full bg-slate-500" />
              <span className="text-xs">时间</span>
            </div>
            {stats?.entities_by_subtype && Object.keys(stats.entities_by_subtype).length > 0 && (
              <>
                <Separator orientation="vertical" className="h-4" />
                <span className="text-xs text-gray-400 shrink-0">细分:</span>
                {Object.entries(stats.entities_by_subtype)
                  .sort(([, a], [, b]) => b - a)
                  .slice(0, 8)
                  .map(([sub, count]) => (
                    <div key={sub} className="flex items-center gap-1 shrink-0">
                      <span className="text-[10px] text-gray-500">{SUBTYPE_LABELS[sub] || sub}({count})</span>
                    </div>
                  ))}
              </>
            )}
          </div>
        </div>
      </div>

      {/* 节点原文出处弹窗 */}
      {popoverEntity && (
        <EntitySourcePopover
          entityName={popoverEntity}
          onClose={() => setPopoverEntity(null)}
          onJumpToArticle={(id) => {
            const name = popoverEntity;
            setPopoverEntity(null);
            window.location.href = `/articles?highlight=${encodeURIComponent(name)}&article=${id}`;
          }}
        />
      )}
    </div>
  );
}

// 使用 Suspense 包装以支持 useSearchParams
export default function KnowledgeGraphPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-screen"><Loader2 className="w-8 h-8 animate-spin" /></div>}>
      <KnowledgeGraphPageContent />
    </Suspense>
  );
}