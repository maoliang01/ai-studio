"use client";

import { useState, useEffect, useRef } from "react";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
  FolderOpen,
  Tags,
  Settings,
  Clock,
  Play,
  Calendar,
  CheckCircle,
  XCircle,
  Eye,
  ChevronUp,
} from "lucide-react";
import type {
  WebsiteCategory,
  ScrapeSource,
  TabNode,
  TabTree,
  Category,
  ScheduledTask,
  ScrapeHistory,
  DailySummary,
  TaskStats,
  ScrapeRangeOption,
  RunningTask,
} from "@/types";

// 默认分类颜色列表
const DEFAULT_COLORS = [
  "#EF4444", "#F97316", "#EAB308", "#22C55E", "#10B981",
  "#14B8A6", "#06B6D4", "#3B82F6", "#6366F1", "#8B5CF6",
  "#A855F7", "#EC4899", "#F43F5E", "#6B7280",
];

// 获取分类颜色样式
const getColorStyle = (color: string) => ({
  backgroundColor: `${color}20`,
  color: color,
  borderColor: `${color}40`,
});

// 判断是否为默认分类
const isDefaultCategory = (id: string) =>
  ["government", "business", "academic"].includes(id);

export default function ScrapeSettingsPage() {
  const {
    scrapeSources,
    categories,
    addScrapeSource,
    updateScrapeSource,
    deleteScrapeSource,
    toggleScrapeSource,
    syncFromBackend,
    addCategory,
    updateCategory,
    deleteCategory,
  } = useSettingsStore();

  // 分类管理相关状态
  const [categoryDialogOpen, setCategoryDialogOpen] = useState(false);
  const [editingCategory, setEditingCategory] = useState<Category | null>(null);
  const [categoryForm, setCategoryForm] = useState({
    name: "",
    color: DEFAULT_COLORS[0],
  });
  const [categoryError, setCategoryError] = useState<string | null>(null);
  const [isSavingCategory, setIsSavingCategory] = useState(false);

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

  // 定时任务相关状态
  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [taskStats, setTaskStats] = useState<TaskStats | null>(null);
  const [history, setHistory] = useState<ScrapeHistory[]>([]);
  const [dailySummary, setDailySummary] = useState<DailySummary[]>([]);
  const [taskDialogOpen, setTaskDialogOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<ScheduledTask | null>(null);
  const [taskForm, setTaskForm] = useState<{
    name: string;
    sourceIds: string[];
    customUrl: string;
    scheduleTime: string;
    scrapeRange: ScrapeRangeOption;
  }>({
    name: "",
    sourceIds: [],
    customUrl: "",
    scheduleTime: "08:00",
    scrapeRange: "1d",
  });
  const [isLoadingTasks, setIsLoadingTasks] = useState(false);
  const [isSavingTask, setIsSavingTask] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [activeTab, setActiveTab] = useState("sources");
  const [expandedHistoryIds, setExpandedHistoryIds] = useState<Set<string>>(new Set());  // 展开的历史记录
  const [runningTasks, setRunningTasks] = useState<RunningTask[]>([]);  // 运行中的任务列表
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);  // 轮询定时器

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("tab") === "scheduled") {
      setActiveTab("scheduled");
    }
  }, []);

  // 加载定时任务数据（使用 ref 确保可在 useEffect 中使用）
  const loadTasksRef = useRef<() => Promise<void>>(async () => {
    console.log("[debug] loadTasksRef 开始加载");
    setIsLoadingTasks(true);
    try {
      const [tasksRes, statsRes, summaryRes] = await Promise.all([
        fetch("/api/scheduled?include_disabled=true"),
        fetch("/api/scheduled/stats"),
        fetch("/api/scheduled/history/summary"),
      ]);
      console.log("[debug] 任务列表API状态:", tasksRes.status);
      if (tasksRes.ok) {
        const data = await tasksRes.json();
        console.log("[debug] 任务列表返回数据:", JSON.stringify(data));
        setTasks(Array.isArray(data) ? data : []);
      }
      if (statsRes.ok) {
        const data = await statsRes.json();
        setTaskStats(data.error ? null : data);
      }
      if (summaryRes.ok) {
        const data = await summaryRes.json();
        setDailySummary(Array.isArray(data) ? data : []);
      }
    } catch (error) {
      console.error("[debug] 加载定时任务失败:", error);
    } finally {
      setIsLoadingTasks(false);
      console.log("[debug] loadTasksRef 加载完成");
    }
  });

  const loadHistoryRef = useRef<() => Promise<void>>(async () => {
    try {
      const res = await fetch("/api/scheduled/history?limit=50");
      if (res.ok) {
        const data = await res.json();
        setHistory(Array.isArray(data) ? data : []);
      }
    } catch (error) {
      console.error("加载历史记录失败:", error);
    }
  });

  // 加载运行中的任务
  const loadRunningTasks = useRef<() => Promise<void>>(async () => {
    try {
      const res = await fetch("/api/scheduled/running");
      if (res.ok) {
        const data = await res.json();
        const activeTasks: RunningTask[] = data.running_tasks || [];
        setRunningTasks(activeTasks);
      }
    } catch (error) {
      console.error("加载运行中任务失败:", error);
    }
  });

  // 格式化已运行时间
  const formatElapsedTime = (seconds?: number) => {
    if (!seconds) return "-";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    if (mins > 0) {
      return `${mins}分${secs}秒`;
    }
    return `${secs}秒`;
  };

  // 当切换到定时爬取选项卡时加载数据并启动轮询
  useEffect(() => {
    if (activeTab === "scheduled") {
      loadTasksRef.current();
      loadRunningTasks.current();

      // 启动轮询（每10秒检查一次）
      if (!pollingIntervalRef.current) {
        pollingIntervalRef.current = setInterval(() => {
          loadRunningTasks.current();
          loadHistoryRef.current();
        }, 10000);
      }
    }

    return () => {
      // 离开选项卡时清除轮询
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [activeTab]);

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

  const getCategoryLabel = (category: string) => {
    // 首先从 categories 列表中查找
    const found = categories.find((c) => c.id === category);
    if (found) return found.name;
    // 兼容旧数据中的默认分类
    const labels: Record<string, string> = {
      government: "党政类",
      business: "商务类",
      academic: "学术类",
    };
    return labels[category] || category;
  };

  const getCategoryColors = (category: WebsiteCategory) => {
    // 首先从 categories 列表中查找颜色
    const found = categories.find((c) => c.id === category);
    if (found) {
      return {
        text: found.color,
        border: `${found.color}30`,
        bg: `${found.color}10`,
      };
    }
    // 兼容旧数据中的默认分类
    const colors: Record<string, { text: string; border: string; bg: string }> = {
      government: { text: "text-red-600", border: "border-red-200", bg: "bg-red-50" },
      business: { text: "text-blue-600", border: "border-blue-200", bg: "bg-blue-50" },
      academic: { text: "text-green-600", border: "border-green-200", bg: "bg-green-50" },
    };
    return colors[category] || { text: "text-gray-600", border: "border-gray-200", bg: "bg-gray-50" };
  };

  // 统计各类型数量
  const stats: Record<string, number> = {
    total: scrapeSources.length,
    ...categories.reduce((acc, cat) => {
      acc[cat.id] = scrapeSources.filter((s) => s.category === cat.id).length;
      return acc;
    }, {} as Record<string, number>),
  };

  // 分类管理函数
  const handleOpenCategoryDialog = (category?: Category) => {
    setCategoryError(null);
    if (category) {
      setEditingCategory(category);
      setCategoryForm({
        name: category.name,
        color: category.color,
      });
    } else {
      setEditingCategory(null);
      setCategoryForm({
        name: "",
        color: DEFAULT_COLORS[Math.floor(Math.random() * DEFAULT_COLORS.length)],
      });
    }
    setCategoryDialogOpen(true);
  };

  const handleSaveCategory = async () => {
    if (!categoryForm.name.trim()) {
      setCategoryError("分类名称不能为空");
      return;
    }

    setIsSavingCategory(true);
    setCategoryError(null);

    try {
      if (editingCategory) {
        // 更新分类
        const success = await updateCategory(editingCategory.id, categoryForm.name.trim(), categoryForm.color);
        if (!success) {
          setCategoryError("更新分类失败");
        }
      } else {
        // 添加分类
        const result = await addCategory(categoryForm.name.trim(), categoryForm.color);
        if (!result) {
          setCategoryError("添加分类失败，名称可能已存在");
        }
      }
    } finally {
      setIsSavingCategory(false);
    }

    if (!categoryError) {
      setCategoryDialogOpen(false);
    }
  };

  const handleDeleteCategory = async (category: Category) => {
    if (category.sourceCount > 0) {
      alert(`该分类下有 ${category.sourceCount} 个来源，无法删除`);
      return;
    }
    if (confirm(`确定要删除分类"${category.name}"吗？`)) {
      await deleteCategory(category.id);
    }
  };

  // 切换任务启用状态
  const handleToggleTask = async (taskId: string) => {
    try {
      const res = await fetch(`/api/scheduled/${taskId}/toggle`, { method: "POST" });
      if (res.ok) {
        setTasks((prev) =>
          prev.map((t) => (t.id === taskId ? { ...t, isEnabled: !t.isEnabled } : t))
        );
      }
    } catch (error) {
      console.error("切换任务状态失败:", error);
    }
  };

  // 启动任务（仅启用，等待定时执行）或立即执行已启用的任务
  const handleToggleOrRunTask = async (task: ScheduledTask) => {
    if (!task.isEnabled) {
      // 任务未启用，点击"启动"按钮：只启用任务，让调度器在定时时间自动执行
      try {
        const res = await fetch(`/api/scheduled/${task.id}/toggle`, { method: "POST" });
        if (res.ok) {
          // 立即更新本地状态
          setTasks((prev) =>
            prev.map((t) => (t.id === task.id ? { ...t, isEnabled: true } : t))
          );
          // 重新加载获取最新的 nextRunAt
          await loadTasksRef.current();
        }
      } catch (error) {
        console.error("启动任务失败:", error);
      }
    } else {
      // 任务已启用，点击"立即执行"：手动触发立即爬取
      try {
        const res = await fetch(`/api/scheduled/${task.id}/run`, { method: "POST" });
        if (res.ok) {
          const data = await res.json();
          await loadHistoryRef.current();
        } else {
          const data = await res.json();
          alert(data.error || "执行失败");
        }
      } catch (error) {
        console.error("执行任务失败:", error);
        alert("执行失败，请检查后端服务");
      }
    }
  };

  // 打开定时任务对话框
  const handleOpenTaskDialog = (task?: ScheduledTask) => {
    const defaultForm = {
      name: "",
      sourceIds: [] as string[],
      customUrl: "",
      scheduleTime: "08:00",
      scrapeRange: "1d" as ScrapeRangeOption,
    };

    if (task) {
      setEditingTask(task);
      setTaskForm({
        name: task.name,
        sourceIds: task.sourceIds || [],
        customUrl: task.customUrl || "",
        scheduleTime: task.scheduleTime,
        scrapeRange: (task.scrapeRange as ScrapeRangeOption) || "1d",
      });
    } else {
      setEditingTask(null);
      setTaskForm(defaultForm);
    }
    setTaskDialogOpen(true);
  };

  // 保存定时任务
  const handleSaveTask = async () => {
    console.log("[debug] handleSaveTask 被调用, taskForm:", JSON.stringify(taskForm));
    if (!taskForm.name.trim()) {
      alert("请输入任务名称");
      return;
    }

    // 验证：至少需要一个URL来源
    const hasSource = taskForm.sourceIds.length > 0 || taskForm.customUrl.trim();
    if (!hasSource) {
      alert("请选择爬取源或输入自定义URL");
      return;
    }

    setIsSavingTask(true);
    try {
      const url = editingTask
        ? `/api/scheduled/${editingTask.id}`
        : "/api/scheduled";
      const method = editingTask ? "PUT" : "POST";

      // 发送 camelCase 到前端 API route（它会转换为 snake_case）
      const body: Record<string, string | string[]> = {
        name: taskForm.name.trim(),
        scheduleTime: taskForm.scheduleTime,
        scrapeRange: taskForm.scrapeRange,
      };

      if (taskForm.sourceIds.length > 0) {
        body.sourceIds = taskForm.sourceIds;
      }
      if (taskForm.customUrl.trim()) {
        body.customUrl = taskForm.customUrl.trim();
      }

      console.log("[debug] 发送请求:", url, method, JSON.stringify(body));
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      console.log("[debug] 响应状态:", res.status);

      if (res.ok) {
        console.log("[debug] 保存成功，开始刷新任务列表");
        await loadTasksRef.current();
        console.log("[debug] 任务列表刷新完成，关闭对话框");
        setTaskDialogOpen(false);
        console.log("[debug] 对话框已关闭");
      } else {
        const data = await res.json();
        console.log("[debug] 保存失败:", data.error);
        alert(data.error || "保存失败");
      }
    } catch (error) {
      console.error("[debug] 保存任务失败:", error);
      alert("保存失败");
    } finally {
      setIsSavingTask(false);
    }
  };

  // 删除定时任务
  const handleDeleteTask = async (taskId: string) => {
    if (confirm("确定要删除这个定时任务吗？")) {
      try {
        const res = await fetch(`/api/scheduled/${taskId}`, { method: "DELETE" });
        if (res.ok) {
          setTasks((prev) => prev.filter((t) => t.id !== taskId));
        }
      } catch (error) {
        console.error("删除任务失败:", error);
      }
    }
  };

  // 格式化时间显示
  const formatTime = (timeStr?: string) => {
    if (!timeStr) return "-";
    const date = new Date(timeStr);
    return date.toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // 获取状态图标
  const getStatusIcon = (status: string) => {
    switch (status) {
      case "success":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "failed":
        return <XCircle className="h-4 w-4 text-red-500" />;
      case "running":
        return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
      default:
        return <Clock className="h-4 w-4 text-gray-400" />;
    }
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
        <div className="grid grid-cols-5 gap-4">
          <Card className="p-4 text-center">
            <p className="text-2xl font-bold">{stats.total}</p>
            <p className="text-xs text-muted-foreground">全部</p>
          </Card>
          {categories.map((cat) => (
            <Card key={cat.id} className="p-4 text-center">
              <p className="text-2xl font-bold" style={{ color: cat.color }}>
                {stats[cat.id] || 0}
              </p>
              <p className="text-xs text-muted-foreground">{cat.name}</p>
            </Card>
          ))}
        </div>

        {/* 主内容区 - 使用选项卡 */}
        <Card className="p-6">
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="mb-4">
              <TabsTrigger value="sources" className="gap-2">
                <Globe className="h-4 w-4" />
                网页来源
              </TabsTrigger>
              <TabsTrigger value="categories" className="gap-2">
                <Tags className="h-4 w-4" />
                分类管理
              </TabsTrigger>
              <TabsTrigger value="scheduled" className="gap-2">
                <Clock className="h-4 w-4" />
                定时爬取
              </TabsTrigger>
            </TabsList>

            {/* 网页来源选项卡 */}
            <TabsContent value="sources">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-semibold">网页来源</h3>
                    <p className="text-sm text-muted-foreground">配置要爬取的网页列表</p>
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
                    {scrapeSources.map((source) => {
                      const colors = getCategoryColors(source.category);
                      return (
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
                                className={cn(colors.text, colors.border, colors.bg)}
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
                      );
                    })}
                  </div>
                )}
              </div>
            </TabsContent>

            {/* 分类管理选项卡 */}
            <TabsContent value="categories">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-semibold">分类管理</h3>
                    <p className="text-sm text-muted-foreground">
                      添加、编辑或删除网页分类，系统会自动创建对应的存储文件夹
                    </p>
                  </div>
                  <Button onClick={() => handleOpenCategoryDialog()} className="gap-2">
                    <Plus className="h-4 w-4" />
                    添加分类
                  </Button>
                </div>

                {categories.length === 0 ? (
                  <div className="text-center py-12 text-muted-foreground">
                    <Tags className="h-16 w-16 mx-auto mb-4 opacity-50" />
                    <p className="mb-1 text-lg">暂无分类</p>
                    <p className="text-sm">点击上方按钮添加分类</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {categories.map((category) => (
                      <div
                        key={category.id}
                        className="flex items-center gap-4 p-4 rounded-lg bg-muted/50 hover:bg-muted transition-colors"
                      >
                        <div
                          className="flex h-10 w-10 items-center justify-center rounded-lg"
                          style={{ backgroundColor: `${category.color}20` }}
                        >
                          <FolderOpen className="h-5 w-5" style={{ color: category.color }} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium">{category.name}</span>
                            <Badge
                              variant="outline"
                              style={getColorStyle(category.color)}
                            >
                              {category.sourceCount} 个来源
                            </Badge>
                            {isDefaultCategory(category.id) && (
                              <Badge variant="secondary" className="text-xs">
                                默认分类
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <FolderOpen className="h-3 w-3" />
                            <span>存储文件夹: {category.folderName}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleOpenCategoryDialog(category)}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          {!isDefaultCategory(category.id) && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteCategory(category)}
                              className="text-destructive hover:text-destructive"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </TabsContent>

            {/* 定时爬取选项卡 */}
            <TabsContent value="scheduled" className="space-y-4">
              {/* 加载数据 */}
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold">定时任务</h3>
                  <p className="text-sm text-muted-foreground">设置每日自动爬取网页</p>
                </div>
                <Button onClick={() => { loadTasksRef.current(); handleOpenTaskDialog(); }} className="gap-2">
                  <Plus className="h-4 w-4" />
                  添加任务
                </Button>
              </div>

              {/* 统计信息 */}
              {taskStats && (
                <div className="grid grid-cols-5 gap-4">
                  <Card className="p-3 text-center">
                    <p className="text-xl font-bold">{taskStats.totalTasks}</p>
                    <p className="text-xs text-muted-foreground">总任务</p>
                  </Card>
                  <Card className="p-3 text-center">
                    <p className="text-xl font-bold text-green-600">{taskStats.enabledTasks}</p>
                    <p className="text-xs text-muted-foreground">已启用</p>
                  </Card>
                  <Card className="p-3 text-center">
                    <p className="text-xl font-bold text-blue-600">{taskStats.todayRuns}</p>
                    <p className="text-xs text-muted-foreground">今日执行</p>
                  </Card>
                  <Card className="p-3 text-center">
                    <p className="text-xl font-bold text-green-600">{taskStats.todaySuccess}</p>
                    <p className="text-xs text-muted-foreground">今日成功</p>
                  </Card>
                  <Card className="p-3 text-center">
                    <p className="text-xl font-bold text-red-600">{taskStats.todayFailed}</p>
                    <p className="text-xs text-muted-foreground">今日失败</p>
                  </Card>
                </div>
              )}

              {/* 运行状态显示 */}
              {runningTasks.length > 0 && (
                <div className="border-2 border-blue-200 bg-blue-50 dark:bg-blue-950/30 rounded-lg p-4 space-y-3">
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                    <span className="text-sm font-medium text-blue-700 dark:text-blue-400">
                      正在运行 ({runningTasks.length})
                    </span>
                    <span className="text-xs text-muted-foreground ml-auto">
                      每10秒自动刷新
                    </span>
                  </div>
                  {runningTasks.map((task) => (
                    <div key={task.id} className="flex items-center gap-4 p-3 bg-white/80 dark:bg-slate-900/50 rounded-lg">
                      <Loader2 className="h-4 w-4 animate-spin text-blue-500 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm">{task.taskName || "定时任务"}</span>
                          <Badge variant="outline" className="text-xs bg-blue-50 border-blue-200 text-blue-700">
                            运行中
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground truncate mt-0.5">
                          {task.url}
                        </p>
                        <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1">
                          <span>开始时间: {formatTime(task.startedAt)}</span>
                          <span>已运行: {formatElapsedTime(task.elapsedSeconds)}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* 任务列表 */}
              {isLoadingTasks ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : tasks.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground border-2 border-dashed rounded-lg">
                  <Clock className="h-16 w-16 mx-auto mb-4 opacity-50" />
                  <p className="mb-1 text-lg">暂无定时任务</p>
                  <p className="text-sm">点击上方按钮创建一个每日自动执行的爬取任务</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {tasks.map((task) => (
                    <div
                      key={task.id}
                      className="flex items-center gap-4 p-4 rounded-lg bg-muted/50 hover:bg-muted transition-colors"
                    >
                      <Switch
                        checked={task.isEnabled}
                        onCheckedChange={() => handleToggleTask(task.id)}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <span className="font-medium">{task.name}</span>
                          <Badge variant="outline">{task.scheduleTime}</Badge>
                          <Badge variant="secondary">{task.scrapeRange || "1d"}</Badge>
                        </div>
                        <p className="text-sm text-muted-foreground truncate">
                          {task.customUrl || (task.sourceNames?.length ? `来源: ${task.sourceNames.join(", ")}` : `来源: ${task.sourceId || "未设置"}`)}
                        </p>
                        <div className="flex items-center gap-4 text-xs text-muted-foreground mt-1">
                          <span>上次执行: {formatTime(task.lastRunAt)}</span>
                          <span>下次执行: {formatTime(task.nextRunAt)}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <Button
                          variant={task.isEnabled ? "default" : "outline"}
                          size="sm"
                          onClick={() => handleToggleOrRunTask(task)}
                          className="gap-1"
                        >
                          <Play className="h-3 w-3" />
                          {task.isEnabled ? "立即执行" : "启动"}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleOpenTaskDialog(task)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteTask(task.id)}
                          className="text-destructive hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* 爬取历史区域 */}
              <div className="border-t pt-4 mt-4">
                <button
                  onClick={() => {
                    if (!showHistory) loadHistoryRef.current();
                    setShowHistory(!showHistory);
                  }}
                  className="flex items-center gap-2 text-sm font-medium mb-3 hover:text-primary transition-colors"
                >
                  {showHistory ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                  <Calendar className="h-4 w-4" />
                  爬取历史
                  {dailySummary.length > 0 && (
                    <Badge variant="secondary" className="ml-2">
                      近{dailySummary.length}天
                    </Badge>
                  )}
                </button>

                {showHistory && (
                  <div className="space-y-4">
                    {/* 每日汇总 */}
                    {dailySummary.length > 0 && (
                      <div className="grid grid-cols-7 gap-2">
                        {dailySummary.map((day) => (
                          <div
                            key={day.date}
                            className={cn(
                              "p-2 rounded-lg text-center text-xs",
                              day.total > 0 ? "bg-muted/50" : "opacity-50"
                            )}
                          >
                            <p className="font-medium">{day.date}</p>
                            <p className="text-muted-foreground">
                              {day.success}/{day.total} 成功
                            </p>
                            <p className="text-muted-foreground">
                              {day.articles} 篇文章
                            </p>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* 历史记录列表 */}
                    {history.length > 0 ? (
                      <div className="space-y-2 max-h-[400px] overflow-y-auto">
                        {history.map((item) => {
                          const isExpanded = expandedHistoryIds.has(item.id);
                          const hasMultipleArticles = item.articleTitle && item.articleTitle.includes('\n');
                          const articleLines = item.articleTitle ? item.articleTitle.split('\n') : [];

                          return (
                            <div
                              key={item.id}
                              className="border rounded-lg p-3 bg-muted/30 hover:bg-muted/50 transition-colors"
                            >
                              {/* 主行 - 可点击展开 */}
                              <div
                                className={cn("flex items-center gap-3", hasMultipleArticles && "cursor-pointer")}
                                onClick={() => {
                                  if (hasMultipleArticles) {
                                    setExpandedHistoryIds(prev => {
                                      const next = new Set(prev);
                                      if (next.has(item.id)) {
                                        next.delete(item.id);
                                      } else {
                                        next.add(item.id);
                                      }
                                      return next;
                                    });
                                  }
                                }}
                              >
                                {getStatusIcon(item.status)}
                                <div className="flex-1 min-w-0">
                                  {/* 显示第一行标题或 URL */}
                                  <p className="text-sm font-medium truncate">
                                    {articleLines[0] || item.url || "无标题"}
                                  </p>
                                  <p className="text-xs text-muted-foreground">
                                    {item.taskName && <span>{item.taskName} · </span>}
                                    {formatTime(item.startedAt)}
                                    {item.articlesCount > 0 && ` · ${item.articlesCount} 篇文章`}
                                  </p>
                                  {item.errorMessage && (
                                    <p className="text-xs text-red-500 mt-1">{item.errorMessage}</p>
                                  )}
                                </div>
                                {hasMultipleArticles && (
                                  <ChevronDown
                                    className={cn(
                                      "h-4 w-4 text-muted-foreground shrink-0 transition-transform",
                                      isExpanded && "rotate-180"
                                    )}
                                  />
                                )}
                              </div>

                              {/* 展开后的文章列表 */}
                              {isExpanded && articleLines.length > 1 && (
                                <div className="mt-3 pl-9 space-y-1.5 border-t pt-3">
                                  <p className="text-xs font-medium text-muted-foreground mb-2">
                                    文章列表：
                                  </p>
                                  {articleLines.map((line, idx) => (
                                    <p key={idx} className="text-xs text-muted-foreground">
                                      <span className="text-muted-foreground/60">{idx + 1}.</span> {line}
                                    </p>
                                  ))}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="text-center text-sm text-muted-foreground py-4">
                        暂无爬取历史记录
                      </p>
                    )}
                  </div>
                )}
              </div>
            </TabsContent>
          </Tabs>
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
                      category: value as string,
                    })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="选择网页种类" />
                  </SelectTrigger>
                  <SelectContent>
                    {categories.map((cat) => (
                      <SelectItem key={cat.id} value={cat.id}>
                        <div className="flex items-center gap-2">
                          <div
                            className="h-2 w-2 rounded-full"
                            style={{ backgroundColor: cat.color }}
                          />
                          {cat.name}
                        </div>
                      </SelectItem>
                    ))}
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

        {/* 分类管理 Dialog */}
        <Dialog open={categoryDialogOpen} onOpenChange={setCategoryDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editingCategory ? "编辑分类" : "添加分类"}
              </DialogTitle>
              <DialogDescription>
                {editingCategory
                  ? "修改分类名称和颜色，对应的存储文件夹将自动更新"
                  : "添加新的网页分类，系统会自动创建对应的存储文件夹"}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-4">
              {/* 分类名称 */}
              <div className="space-y-2">
                <Label htmlFor="category-name">
                  分类名称 <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="category-name"
                  value={categoryForm.name}
                  onChange={(e) => setCategoryForm({ ...categoryForm, name: e.target.value })}
                  placeholder="例如：新闻媒体"
                />
              </div>

              {/* 分类颜色 */}
              <div className="space-y-2">
                <Label>分类颜色</Label>
                <div className="flex flex-wrap gap-2">
                  {DEFAULT_COLORS.map((color) => (
                    <button
                      key={color}
                      type="button"
                      onClick={() => setCategoryForm({ ...categoryForm, color })}
                      className={cn(
                        "h-8 w-8 rounded-full transition-transform",
                        categoryForm.color === color
                          ? "ring-2 ring-offset-2 ring-primary scale-110"
                          : "hover:scale-105"
                      )}
                      style={{ backgroundColor: color }}
                    />
                  ))}
                </div>
              </div>

              {/* 错误提示 */}
              {categoryError && (
                <div className="flex items-center gap-2 text-destructive text-sm">
                  <AlertCircle className="h-4 w-4" />
                  {categoryError}
                </div>
              )}

              {/* 预览 */}
              <div className="p-3 rounded-lg bg-muted/50">
                <p className="text-sm text-muted-foreground mb-2">预览</p>
                <Badge
                  variant="outline"
                  style={getColorStyle(categoryForm.color)}
                >
                  {categoryForm.name || "分类名称"}
                </Badge>
                <p className="text-xs text-muted-foreground mt-2">
                  存储文件夹: {categoryForm.name
                    ? categoryForm.name.replace(/[^\w\s一-龥]/g, "").replace(/\s/g, "_") || "untitled"
                    : "未命名"}
                </p>
              </div>
            </div>

            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setCategoryDialogOpen(false)}
              >
                取消
              </Button>
              <Button
                onClick={handleSaveCategory}
                disabled={isSavingCategory || !categoryForm.name.trim()}
              >
                {isSavingCategory && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                {editingCategory ? "保存" : "添加"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* 定时任务 Dialog */}
        <Dialog open={taskDialogOpen} onOpenChange={setTaskDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editingTask ? "编辑定时任务" : "添加定时任务"}
              </DialogTitle>
              <DialogDescription>
                设置每日自动爬取网页的时间和目标网站
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-4">
              {/* 任务名称 */}
              <div className="space-y-2">
                <Label htmlFor="task-name">
                  任务名称 <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="task-name"
                  value={taskForm.name}
                  onChange={(e) => setTaskForm({ ...taskForm, name: e.target.value })}
                  placeholder="例如：每日新闻爬取"
                />
              </div>

              {/* 爬取来源（按分类分组） */}
              <div className="space-y-2">
                <Label>爬取来源（按分类分组）</Label>
                {scrapeSources.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-2">暂无已配置的爬取源，请先在「网页来源」中添加</p>
                ) : (
                  <div className="border rounded-lg p-3 max-h-[200px] overflow-y-auto space-y-2">
                    {categories.map((cat) => {
                      // 过滤出该分类下的爬取源
                      const catSources = scrapeSources.filter(s => s.category === cat.id);
                      if (catSources.length === 0) return null;

                      return (
                        <div key={cat.id} className="border rounded-md p-2 bg-muted/20">
                          {/* 分类标题 */}
                          <div className="flex items-center gap-2 mb-2 px-1">
                            <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: cat.color }} />
                            <span className="text-sm font-medium">{cat.name}</span>
                            <Badge variant="secondary" className="ml-auto text-xs">{catSources.length}</Badge>
                          </div>
                          {/* 该分类下的爬取源 */}
                          <div className="space-y-1 pl-4">
                            {catSources.map((source) => (
                              <div key={source.id} className="flex items-center gap-2">
                                <Checkbox
                                  id={`source-${source.id}`}
                                  checked={taskForm.sourceIds.includes(source.id)}
                                  onCheckedChange={(checked) => {
                                    if (checked) {
                                      setTaskForm({
                                        ...taskForm,
                                        sourceIds: [...taskForm.sourceIds, source.id],
                                      });
                                    } else {
                                      setTaskForm({
                                        ...taskForm,
                                        sourceIds: taskForm.sourceIds.filter((id) => id !== source.id),
                                      });
                                    }
                                  }}
                                />
                                <Label
                                  htmlFor={`source-${source.id}`}
                                  className="text-sm cursor-pointer flex items-center gap-2"
                                >
                                  <Globe className="h-3 w-3 text-muted-foreground shrink-0" />
                                  <span className="truncate">{source.name}</span>
                                </Label>
                              </div>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                    {/* 未分类的爬取源 */}
                    {(() => {
                      const uncategorized = scrapeSources.filter(s => !categories.some(c => c.id === s.category));
                      if (uncategorized.length === 0) return null;
                      return (
                        <div className="border rounded-md p-2 bg-muted/20">
                          <div className="flex items-center gap-2 mb-2 px-1">
                            <div className="w-2 h-2 rounded-full bg-gray-400 shrink-0" />
                            <span className="text-sm font-medium">未分类</span>
                            <Badge variant="secondary" className="ml-auto text-xs">{uncategorized.length}</Badge>
                          </div>
                          <div className="space-y-1 pl-4">
                            {uncategorized.map((source) => (
                              <div key={source.id} className="flex items-center gap-2">
                                <Checkbox
                                  id={`source-${source.id}`}
                                  checked={taskForm.sourceIds.includes(source.id)}
                                  onCheckedChange={(checked) => {
                                    if (checked) {
                                      setTaskForm({ ...taskForm, sourceIds: [...taskForm.sourceIds, source.id] });
                                    } else {
                                      setTaskForm({ ...taskForm, sourceIds: taskForm.sourceIds.filter((id) => id !== source.id) });
                                    }
                                  }}
                                />
                                <Label htmlFor={`source-${source.id}`} className="text-sm cursor-pointer flex items-center gap-2">
                                  <Globe className="h-3 w-3 text-muted-foreground shrink-0" />
                                  <span className="truncate">{source.name}</span>
                                </Label>
                              </div>
                            ))}
                          </div>
                        </div>
                      );
                    })()}
                  </div>
                )}
                <p className="text-xs text-muted-foreground">选择已配置的网页来源，或使用下面的自定义URL</p>
              </div>

              {/* 自定义URL */}
              <div className="space-y-2">
                <Label htmlFor="task-url">自定义URL</Label>
                <Input
                  id="task-url"
                  value={taskForm.customUrl}
                  onChange={(e) => setTaskForm({ ...taskForm, customUrl: e.target.value })}
                  placeholder="https://example.com 或留空使用上方选择的来源"
                  type="url"
                />
                <p className="text-xs text-muted-foreground">如果填写了自定义URL，将优先使用此URL</p>
              </div>

              {/* 爬取范围 */}
              <div className="space-y-2">
                <Label>爬取范围</Label>
                <div className="flex gap-2 flex-wrap">
                  {(["1d", "7d", "30d"] as const).map((range) => (
                    <Button
                      key={range}
                      variant={taskForm.scrapeRange === range ? "default" : "outline"}
                      size="sm"
                      onClick={() => setTaskForm({ ...taskForm, scrapeRange: range })}
                      className="gap-1"
                    >
                      {range === "1d" && "前一天"}
                      {range === "7d" && "前一周"}
                      {range === "30d" && "前一月"}
                    </Button>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">
                  设置爬取内容的时间范围，例如「前一天」表示爬取最近24小时内更新的文章
                </p>
              </div>

              {/* 定时时间 */}
              <div className="space-y-2">
                <Label htmlFor="task-time">
                  每日执行时间 <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="task-time"
                  type="time"
                  value={taskForm.scheduleTime}
                  onChange={(e) => setTaskForm({ ...taskForm, scheduleTime: e.target.value })}
                />
                <p className="text-xs text-muted-foreground">
                  设置每天自动执行爬取的时间，例如 08:00 表示每天早上8点执行
                </p>
              </div>
            </div>

            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setTaskDialogOpen(false)}
              >
                取消
              </Button>
              <Button
                onClick={handleSaveTask}
                disabled={isSavingTask || !taskForm.name.trim()}
              >
                {isSavingTask && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                {editingTask ? "保存" : "添加"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
