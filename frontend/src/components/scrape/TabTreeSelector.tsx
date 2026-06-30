"use client";

import { useState, useMemo } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import type { TabNode } from "@/types";
import {
  ChevronRight,
  ChevronDown,
  Globe,
  Loader2,
  AlertCircle,
  UnfoldVertical,
  Target,
} from "lucide-react";

interface TabTreeSelectorProps {
  /** 页签树数据 */
  tree?: {
    domain: string;
    siteTitle: string;
    root: TabNode;
    allNodes: TabNode[];
    totalCount: number;
  };
  /** 是否正在加载 */
  isLoading?: boolean;
  /** 错误信息 */
  error?: string;
  /** 选中的节点ID列表 */
  selectedIds: string[];
  /** 选中状态变化回调 */
  onSelectionChange: (selectedIds: string[]) => void;
  /** 开始爬取回调 */
  onScrape: (selectedIds: string[]) => void;
  /** 是否禁用 */
  disabled?: boolean;
}

/**
 * 分类树节点渲染组件
 */
function TreeNode({
  node,
  depth,
  expandedIds,
  selectedIds,
  onToggleExpand,
  onToggleSelect,
  disabled,
  maxDepth = 3,
}: {
  node: TabNode;
  depth: number;
  expandedIds: Set<string>;
  selectedIds: string[];
  onToggleExpand: (nodeId: string) => void;
  onToggleSelect: (nodeId: string, checked: boolean) => void;
  disabled?: boolean;
  maxDepth?: number;
}) {
  const isExpanded = expandedIds.has(node.id);
  const hasChildren = node.children && node.children.length > 0;
  const isSelected = selectedIds.includes(node.id);
  const canSelect = node.type === "nav";
  const indent = depth * 20;
  const isMaxDepth = depth >= maxDepth;

  // 类型图标
  const TypeIcon = {
    nav: <Globe className="h-4 w-4 text-blue-500 shrink-0" />,
    tab: <Target className="h-4 w-4 text-green-500 shrink-0" />,
    breadcrumb: <ChevronRight className="h-3 w-3 text-gray-400 shrink-0" />,
  };

  // 类型标签颜色
  const typeColors = {
    nav: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
    tab: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
    breadcrumb: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
  };

  return (
    <div className="select-none">
      {/* 节点行 */}
      <div
        className={cn(
          "flex items-center gap-2 py-2 px-3 rounded-md cursor-pointer transition-colors",
          isSelected && canSelect && "bg-primary/10",
          !disabled && canSelect && "hover:bg-accent",
          disabled && "opacity-60 cursor-not-allowed"
        )}
        style={{ paddingLeft: `${indent + 12}px` }}
        onClick={(e) => {
          e.stopPropagation();
          if (hasChildren && !isMaxDepth) {
            onToggleExpand(node.id);
          }
        }}
      >
        {/* 展开/折叠按钮 */}
        {hasChildren && !isMaxDepth ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onToggleExpand(node.id);
            }}
            className="w-5 h-5 flex items-center justify-center hover:bg-accent rounded"
          >
            {isExpanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4 rotate-[-90deg]" />
            )}
          </button>
        ) : (
          <div className="w-5" />
        )}

        {/* 选择框（仅导航类型可选） */}
        <Checkbox
          checked={isSelected}
          onCheckedChange={(checked) => {
            if (canSelect) {
              onToggleSelect(node.id, checked as boolean);
            }
          }}
          disabled={disabled || !canSelect}
          className="shrink-0"
          onClick={(e) => e.stopPropagation()}
        />

        {/* 类型图标 */}
        {TypeIcon[node.type as keyof typeof TypeIcon]}

        {/* 标签 */}
        <span
          className={cn(
            "flex-1 text-sm truncate",
            node.level === 0 && "font-semibold",
            node.level === 1 && "font-medium"
          )}
          title={node.label}
        >
          {node.label}
        </span>

        {/* 类型标签 */}
        {node.level > 0 && (
          <Badge
            variant="outline"
            className={cn("text-xs shrink-0", typeColors[node.type as keyof typeof typeColors])}
          >
            {node.type === "nav" ? "导航" : node.type === "tab" ? "Tab" : "面包屑"}
          </Badge>
        )}

        {/* 子节点数量 */}
        {hasChildren && (
          <Badge variant="secondary" className="text-xs shrink-0">
            {node.children!.length}
          </Badge>
        )}
      </div>

      {/* 子节点 */}
      {hasChildren && isExpanded && !isMaxDepth && (
        <div>
          {node.children!.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              expandedIds={expandedIds}
              selectedIds={selectedIds}
              onToggleExpand={onToggleExpand}
              onToggleSelect={onToggleSelect}
              disabled={disabled}
              maxDepth={maxDepth}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * 页签分类树选择器组件
 *
 * 展示网站的多级页签结构，支持：
 * - 展开/折叠节点
 * - 多选分类
 * - 显示选中数量统计
 */
export function TabTreeSelector({
  tree,
  isLoading,
  error,
  selectedIds,
  onSelectionChange,
  onScrape,
  disabled,
}: TabTreeSelectorProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  // 统计导航分类
  const navCategories = useMemo(() => {
    if (!tree) return [];
    return tree.allNodes.filter((n) => n.type === "nav");
  }, [tree]);

  const selectedNavCount = useMemo(() => {
    return selectedIds.filter((id) => navCategories.some((c) => c.id === id)).length;
  }, [selectedIds, navCategories]);

  // 切换展开状态
  const toggleExpand = (nodeId: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  };

  // 切换选择状态
  const toggleSelect = (nodeId: string, checked: boolean) => {
    if (checked) {
      onSelectionChange([...selectedIds, nodeId]);
    } else {
      onSelectionChange(selectedIds.filter((id) => id !== nodeId));
    }
  };

  // 全选
  const selectAll = () => {
    if (!tree) return;
    const topLevelIds = (tree.root.children || [])
      .filter((c) => c.type === "nav")
      .map((c) => c.id);
    onSelectionChange(topLevelIds);
  };

  // 取消全选
  const deselectAll = () => {
    onSelectionChange([]);
  };

  // 展开全部
  const expandAll = () => {
    if (!tree) return;
    const allIds = new Set<string>();
    const collectIds = (node: TabNode) => {
      if (node.children && node.children.length > 0) {
        allIds.add(node.id);
        node.children.forEach(collectIds);
      }
    };
    (tree.root.children || []).forEach(collectIds);
    setExpandedIds(allIds);
  };

  // 折叠全部
  // const collapseAll = () => {
  //   setExpandedIds(new Set());
  // };

  return (
    <div className="border rounded-lg overflow-hidden bg-card">
      {/* 头部 */}
      <div className="p-4 bg-muted/50 border-b flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 min-w-0">
          <Globe className="h-5 w-5 shrink-0" />
          <span className="font-medium truncate">
            {tree ? tree.siteTitle : "页签分类树"}
          </span>
          {tree && (
            <Badge variant="secondary" className="shrink-0">
              {tree.totalCount} 个分类
            </Badge>
          )}
        </div>

        {tree && (
          <div className="flex items-center gap-2 shrink-0">
            <Button variant="outline" size="sm" onClick={selectAll}>
              全选
            </Button>
            <Button variant="outline" size="sm" onClick={deselectAll}>
              取消
            </Button>
            <Separator orientation="vertical" className="h-6" />
            <Button variant="ghost" size="sm" onClick={expandAll} title="展开全部">
              <UnfoldVertical className="h-4 w-4" />
            </Button>
            <Badge className="bg-primary/10 text-primary border-primary/20">
              已选 {selectedNavCount}/{navCategories.length}
            </Badge>
          </div>
        )}
      </div>

      {/* 内容区 */}
      <div className="p-2">
        {isLoading ? (
          <div className="flex items-center justify-center py-12 gap-3 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span>正在分析页面结构...</span>
          </div>
        ) : error ? (
          <div className="flex items-start gap-3 p-4 text-destructive">
            <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">分析失败</p>
              <p className="text-sm text-muted-foreground mt-1">{error}</p>
            </div>
          </div>
        ) : tree ? (
          <ScrollArea className="h-[350px]">
            <div className="pr-4">
              {/* 渲染根节点的子节点（顶级分类） */}
              {(tree.root.children || []).map((child) => (
                <TreeNode
                  key={child.id}
                  node={child}
                  depth={0}
                  expandedIds={expandedIds}
                  selectedIds={selectedIds}
                  onToggleExpand={toggleExpand}
                  onToggleSelect={toggleSelect}
                  disabled={disabled}
                  maxDepth={3}
                />
              ))}
            </div>
          </ScrollArea>
        ) : (
          <div className="text-center py-12 text-muted-foreground">
            <Globe className="h-12 w-12 mx-auto mb-3 opacity-30" />
            <p>输入 URL 后点击&quot;识别页签&quot;按钮分析页面结构</p>
          </div>
        )}
      </div>

      {/* 底部操作栏 */}
      {tree && selectedNavCount > 0 && (
        <div className="p-4 border-t bg-muted/30">
          <Button
            onClick={() => onScrape(selectedIds)}
            disabled={disabled}
            className="w-full"
            size="lg"
          >
            <Target className="h-4 w-4 mr-2" />
            开始爬取选中的 {selectedNavCount} 个分类
          </Button>
          <p className="text-xs text-muted-foreground text-center mt-2">
            将使用深度爬取模式，逐个爬取选中分类下的所有文章
          </p>
        </div>
      )}
    </div>
  );
}