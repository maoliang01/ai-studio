"use client";

import { useState, useEffect } from "react";
import { useSettingsStore } from "@/stores/settings-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import {
  Globe,
  Plus,
  Pencil,
  Trash2,
  ExternalLink,
  Loader2,
  Target,
  ChevronRight,
  ChevronDown,
  AlertCircle,
} from "lucide-react";
import type { WebsiteCategory, ScrapeSource, TabNode, TabTree } from "@/types";

export default function ScrapeSettingsPage() {
  const {
    scrapeSources,
    addScrapeSource,
    updateScrapeSource,
    deleteScrapeSource,
    toggleScrapeSource,
    syncFromBackend,
  } = useSettingsStore();

  // 组件挂载时从后端同步数据
  useEffect(() => {
    syncFromBackend();
  }, [syncFromBackend]);

  const [scrapeDialogOpen, setScrapeDialogOpen] = useState(false);
  const [editingScrapeSource, setEditingScrapeSource] = useState<ScrapeSource | null>(null);
  const [scrapeForm, setScrapeForm] = useState({
    name: "",
    url: "",
    category: "business" as WebsiteCategory,
    description: "",
    isEnabled: true,
  });

  // 页签分析相关状态
  const [isAnalyzingTabs, setIsAnalyzingTabs] = useState(false);
  const [tabTree, setTabTree] = useState<TabTree | null>(null);
  const [tabError, setTabError] = useState<string | null>(null);
  const [expandedTabIds, setExpandedTabIds] = useState<Set<string>>(new Set());
  const [selectedTabId, setSelectedTabId] = useState<string | null>(null);

  // 调用页签分析 API
  const analyzeUrlTabs = async (url: string) => {
    setIsAnalyzingTabs(true);
    setTabError(null);
    setTabTree(null);
    setSelectedTabId(null);
    setExpandedTabIds(new Set());

    try {
      const res = await fetch("/api/scrape/tabs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, include_nav: true, include_tabs: true }),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || `分析失败: ${res.status}`);
      }

      const data = await res.json();
      if (data.success && data.tree) {
        setTabTree(data.tree);
      } else {
        throw new Error(data.error || "分析失败");
      }
    } catch (error) {
      setTabError(error instanceof Error ? error.message : "分析失败");
    } finally {
      setIsAnalyzingTabs(false);
    }
  };

  // 处理 URL 输入变化时自动分析（可选）
  const handleUrlChange = (url: string) => {
    setScrapeForm({ ...scrapeForm, url });
  };

  // 手动触发页签分析
  const handleAnalyzeTabs = () => {
    if (scrapeForm.url.trim()) {
      analyzeUrlTabs(scrapeForm.url.trim());
    }
  };

  // 选择某个分类
  const handleSelectTab = (tab: TabNode) => {
    setSelectedTabId(tab.id);
    // 自动填充名称（如果名称为空）
    // 同时更新 URL 为选中分类的 URL
    const updates: Partial<typeof scrapeForm> = {};
    if (!scrapeForm.name.trim() && tab.label) {
      updates.name = tab.label;
    }
    // 使用分类的 URL（如果分类有 URL 且有效）
    if (tab.url && tab.url.startsWith("http")) {
      updates.url = tab.url;
    }
    if (Object.keys(updates).length > 0) {
      setScrapeForm({ ...scrapeForm, ...updates });
    }
  };

  // 切换展开状态
  const toggleExpand = (nodeId: string) => {
    setExpandedTabIds((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  };

  const handleOpenScrapeDialog = (source?: ScrapeSource) => {
    if (source) {
      setEditingScrapeSource(source);
      setScrapeForm({
        name: source.name,
        url: source.url,
        category: source.category,
        description: source.description || "",
        isEnabled: source.isEnabled,
      });
    } else {
      setEditingScrapeSource(null);
      setScrapeForm({
        name: "",
        url: "",
        category: "business",
        description: "",
        isEnabled: true,
      });
    }
    // 重置页签分析状态
    setTabTree(null);
    setTabError(null);
    setSelectedTabId(null);
    setExpandedTabIds(new Set());
    setScrapeDialogOpen(true);
  };

  const handleSaveScrapeSource = () => {
    if (!scrapeForm.name.trim() || !scrapeForm.url.trim()) return;

    if (editingScrapeSource) {
      updateScrapeSource(editingScrapeSource.id, scrapeForm);
    } else {
      addScrapeSource(scrapeForm);
    }
    setScrapeDialogOpen(false);
  };

  const getCategoryLabel = (category: WebsiteCategory) => {
    const labels: Record<WebsiteCategory, string> = {
      government: "党政类",
      business: "商务类",
      academic: "学术类",
    };
    return labels[category];
  };

  const getCategoryColors = (category: WebsiteCategory) => {
    const colors: Record<WebsiteCategory, string> = {
      government: "text-red-600 border-red-200 bg-red-50",
      business: "text-blue-600 border-blue-200 bg-blue-50",
      academic: "text-green-600 border-green-200 bg-green-50",
    };
    return colors[category];
  };

  // 统计各类型数量
  const stats = {
    total: scrapeSources.length,
    government: scrapeSources.filter((s) => s.category === "government").length,
    business: scrapeSources.filter((s) => s.category === "business").length,
    academic: scrapeSources.filter((s) => s.category === "academic").length,
  };

  // 渲染页签树节点
  const renderTabNode = (node: TabNode, depth: number = 0) => {
    const isExpanded = expandedTabIds.has(node.id);
    const hasChildren = node.children && node.children.length > 0;
    const isSelected = selectedTabId === node.id;
    const indent = depth * 16;

    return (
      <div key={node.id}>
        <div
          className={cn(
            "flex items-center gap-2 py-1.5 px-2 rounded cursor-pointer transition-colors",
            isSelected ? "bg-primary/10" : "hover:bg-accent",
            node.url ? "" : "opacity-50"
          )}
          style={{ paddingLeft: `${indent + 8}px` }}
          onClick={() => node.url && handleSelectTab(node)}
        >
          {hasChildren ? (
            <button
              onClick={(e) => {
                e.stopPropagation();
                toggleExpand(node.id);
              }}
              className="w-4 h-4 flex items-center justify-center"
            >
              {isExpanded ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
            </button>
          ) : (
            <div className="w-4" />
          )}

          <Checkbox
            checked={isSelected}
            onCheckedChange={() => {
              if (node.url) handleSelectTab(node);
            }}
            disabled={!node.url}
            className="shrink-0"
            onClick={(e) => e.stopPropagation()}
          />

          <span className={cn("text-sm truncate", node.level === 0 && "font-medium")}>
            {node.label}
          </span>

          {node.url && (
            <span className="text-xs text-muted-foreground truncate ml-auto">
              {node.url.length > 25 ? "..." + node.url.slice(-25) : node.url}
            </span>
          )}
        </div>

        {hasChildren && isExpanded && node.children!.map((child) => renderTabNode(child, depth + 1))}
      </div>
    );
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        {/* 页面标题 */}
        <div>
          <h1 className="text-2xl font-semibold mb-2">网页爬取配置</h1>
          <p className="text-muted-foreground">管理要爬取的网页来源，支持分类管理</p>
        </div>

        {/* 统计卡片 */}
        <div className="grid grid-cols-4 gap-4">
          <Card className="p-4 text-center">
            <p className="text-2xl font-bold">{stats.total}</p>
            <p className="text-xs text-muted-foreground">全部</p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-2xl font-bold text-red-600">{stats.government}</p>
            <p className="text-xs text-muted-foreground">党政类</p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-2xl font-bold text-blue-600">{stats.business}</p>
            <p className="text-xs text-muted-foreground">商务类</p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-2xl font-bold text-green-600">{stats.academic}</p>
            <p className="text-xs text-muted-foreground">学术类</p>
          </Card>
        </div>

        {/* 爬取源列表 */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <Globe className="h-5 w-5 text-primary" />
              </div>
              <div>
                <h2 className="text-lg font-semibold">网页来源</h2>
                <p className="text-sm text-muted-foreground">
                  配置要爬取的网页列表
                </p>
              </div>
            </div>
            <Button onClick={() => handleOpenScrapeDialog()} className="gap-2">
              <Plus className="h-4 w-4" />
              添加网页
            </Button>
          </div>

          {scrapeSources.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Globe className="h-16 w-16 mx-auto mb-4 opacity-50" />
              <p className="mb-1 text-lg">暂无配置的网页来源</p>
              <p className="text-sm">点击上方按钮添加要爬取的网页</p>
            </div>
          ) : (
            <div className="space-y-3">
              {scrapeSources.map((source) => (
                <div
                  key={source.id}
                  className="flex items-center gap-4 p-4 rounded-lg bg-muted/50 hover:bg-muted transition-colors"
                >
                  <Switch
                    checked={source.isEnabled}
                    onCheckedChange={() => toggleScrapeSource(source.id)}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium">{source.name}</span>
                      <Badge
                        variant="outline"
                        className={getCategoryColors(source.category)}
                      >
                        {getCategoryLabel(source.category)}
                      </Badge>
                    </div>
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-muted-foreground hover:text-primary flex items-center gap-1 truncate"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                      {source.url}
                    </a>
                    {source.description && (
                      <p className="text-xs text-muted-foreground mt-2 line-clamp-1">
                        {source.description}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleOpenScrapeDialog(source)}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => deleteScrapeSource(source.id)}
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* 爬取源配置 Dialog */}
        <Dialog open={scrapeDialogOpen} onOpenChange={setScrapeDialogOpen}>
          <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-hidden flex flex-col">
            <DialogHeader>
              <DialogTitle>
                {editingScrapeSource ? "编辑网页来源" : "添加网页来源"}
              </DialogTitle>
              <DialogDescription>
                配置要爬取的网页信息，添加时可点击&quot;识别页签&quot;自动分析网站结构
              </DialogDescription>
            </DialogHeader>

            <div className="flex-1 overflow-y-auto space-y-4 py-4">
              {/* 网页 URL */}
              <div className="space-y-2">
                <Label htmlFor="scrape-url">
                  网页地址 <span className="text-destructive">*</span>
                </Label>
                <div className="flex gap-2">
                  <Input
                    id="scrape-url"
                    value={scrapeForm.url}
                    onChange={(e) => handleUrlChange(e.target.value)}
                    placeholder="https://example.com"
                    type="url"
                    className="flex-1"
                  />
                  {!editingScrapeSource && (
                    <Button
                      variant="outline"
                      onClick={handleAnalyzeTabs}
                      disabled={isAnalyzingTabs || !scrapeForm.url.trim()}
                      className="gap-1 shrink-0"
                    >
                      {isAnalyzingTabs ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          分析中
                        </>
                      ) : (
                        <>
                          <Target className="h-4 w-4" />
                          识别页签
                        </>
                      )}
                    </Button>
                  )}
                </div>
              </div>

              {/* 页签分析结果 */}
              {(isAnalyzingTabs || tabTree || tabError) && (
                <div className="border rounded-lg overflow-hidden">
                  <div className="bg-muted/50 px-3 py-2 border-b flex items-center gap-2">
                    <Target className="h-4 w-4 text-primary" />
                    <span className="text-sm font-medium">
                      {isAnalyzingTabs ? "正在分析页面结构..." : tabError ? "分析失败" : `识别到 ${tabTree?.totalCount || 0} 个分类`}
                    </span>
                  </div>

                  {isAnalyzingTabs ? (
                    <div className="flex items-center justify-center py-8 text-muted-foreground">
                      <Loader2 className="h-5 w-5 animate-spin mr-2" />
                      <span>正在分析页面结构...</span>
                    </div>
                  ) : tabError ? (
                    <div className="flex items-start gap-2 p-4 text-destructive">
                      <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                      <span className="text-sm">{tabError}</span>
                    </div>
                  ) : tabTree ? (
                    <ScrollArea className="h-[250px]">
                      <div className="p-2">
                        <p className="text-xs text-muted-foreground px-2 mb-2">
                          选择一个分类后，将自动填充该 URL
                        </p>
                        {(tabTree.root.children || []).map((child) => renderTabNode(child))}
                        {(tabTree.root.children || []).length === 0 && (
                          <p className="text-sm text-muted-foreground text-center py-4">
                            未识别到可爬取的分类
                          </p>
                        )}
                      </div>
                    </ScrollArea>
                  ) : null}
                </div>
              )}

              {/* 网页名称 */}
              <div className="space-y-2">
                <Label htmlFor="scrape-name">
                  网页名称 <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="scrape-name"
                  value={scrapeForm.name}
                  onChange={(e) =>
                    setScrapeForm({ ...scrapeForm, name: e.target.value })
                  }
                  placeholder="例如：某政府官网"
                />
              </div>

              {/* 网页种类 */}
              <div className="space-y-2">
                <Label htmlFor="scrape-category">网页种类</Label>
                <Select
                  value={scrapeForm.category}
                  onValueChange={(value) =>
                    setScrapeForm({
                      ...scrapeForm,
                      category: value as WebsiteCategory,
                    })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="选择网页种类" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="government">党政类</SelectItem>
                    <SelectItem value="business">商务类</SelectItem>
                    <SelectItem value="academic">学术类</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* 描述 */}
              <div className="space-y-2">
                <Label htmlFor="scrape-description">描述（可选）</Label>
                <Textarea
                  id="scrape-description"
                  value={scrapeForm.description}
                  onChange={(e) =>
                    setScrapeForm({ ...scrapeForm, description: e.target.value })
                  }
                  placeholder="简要描述这个网页来源..."
                  rows={2}
                />
              </div>

              {/* 启用开关 */}
              <div className="flex items-center gap-2">
                <Switch
                  checked={scrapeForm.isEnabled}
                  onCheckedChange={(checked) =>
                    setScrapeForm({ ...scrapeForm, isEnabled: checked })
                  }
                />
                <Label className="cursor-pointer">默认启用爬取</Label>
              </div>
            </div>

            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setScrapeDialogOpen(false)}
              >
                取消
              </Button>
              <Button
                onClick={handleSaveScrapeSource}
                disabled={!scrapeForm.name.trim() || !scrapeForm.url.trim()}
              >
                {editingScrapeSource ? "保存" : "添加"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}