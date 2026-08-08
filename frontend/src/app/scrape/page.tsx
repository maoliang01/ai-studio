"use client";

import { useState, useEffect } from "react";
import { useScrapeStore } from "@/stores/scrape-store";
import { useSettingsStore } from "@/stores/settings-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { DateRangeSelector } from "@/components/scrape/DateRangeSelector";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Globe,
  Link2,
  Copy,
  Download,
  ChevronDown,
  ChevronUp,
  Clock,
  CheckCircle2,
  AlertCircle,
  Loader2,
  History,
  Trash2,
  User,
  Calendar,
  Tag,
  AlignLeft,
  Eye,
  EyeOff,
  Layers,
  FileDown,
  Sparkles,
  StopCircle,
  Bookmark,
  ExternalLink,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ScrapeResult, DateRangeValue, ScrapeLevel, ScrapeSource, WebsiteCategory } from "@/types";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useRouter } from "next/navigation";

// 动态获取分类标签的辅助函数
const getCategoryLabel = (category: WebsiteCategory, categories?: { id: string; name: string }[]) => {
  // 如果有动态 categories，优先从 categories 中获取
  if (categories) {
    const matched = categories.find(c => c.id === category);
    if (matched) return matched.name;
  }
  // 兼容固定的 government/business/academic
  const labels: Record<WebsiteCategory, string> = {
    government: "党政",
    business: "商务",
    academic: "学术",
  };
  return labels[category] || category;
};

// 动态获取分类颜色的辅助函数
const getCategoryColors = (category: WebsiteCategory, categories?: { id: string; color: string }[]) => {
  // 如果有动态 categories，使用其颜色
  if (categories) {
    const matched = categories.find(c => c.id === category);
    if (matched?.color) return matched.color;
  }
  // 兼容固定的 government/business/academic
  const colors: Record<WebsiteCategory, string> = {
    government: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
    business: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
    academic: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  };
  return colors[category] || "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300";
};

export default function ScrapePage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [expandedCard, setExpandedCard] = useState<string | null>(null);
  const [maxArticles, setMaxArticles] = useState(10);
  const [dateRange, setDateRange] = useState<DateRangeValue | undefined>();
  const [scrapeLevel, setScrapeLevel] = useState<ScrapeLevel>("deep");
  const [advancedOptions, setAdvancedOptions] = useState({
    extractContent: true,
    fetchHtml: false,
    preserveFormat: false,
    maxDepth: 0,
    timeout: 30,
  });
  const [selectedSource, setSelectedSource] = useState<ScrapeSource | null>(null);
  const [showSourceSelector, setShowSourceSelector] = useState(false);
  const [scheduleDialogOpen, setScheduleDialogOpen] = useState(false);
  const [scheduleTime, setScheduleTime] = useState("08:00");
  const [scheduleRange, setScheduleRange] = useState<"1d" | "7d" | "30d">("1d");
  const [isSavingSchedule, setIsSavingSchedule] = useState(false);
  const [scheduleMessage, setScheduleMessage] = useState<string | null>(null);
  // 定时任务多选相关状态
  const [selectedSources, setSelectedSources] = useState<ScrapeSource[]>([]);
  const [customUrlInput, setCustomUrlInput] = useState("");
  const [recentHistory, setRecentHistory] = useState<any[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  // 用于批量导出的选中状态
  const [selectedForExport, setSelectedForExport] = useState<Set<string>>(new Set());

  const [selectedCategory, setSelectedCategory] = useState<string>("");  // 保存到数据库的分类
  const [isExporting, setIsExporting] = useState(false);
  const [exportSuccess, setExportSuccess] = useState<string | null>(null);

  // Cookie 输入相关状态
  const [showCookieDialog, setShowCookieDialog] = useState(false);
  const [cookieInput, setCookieInput] = useState("");
  const [pendingScrapeParams, setPendingScrapeParams] = useState<{
    url: string;
    isDeepScrape: boolean;
    options?: any;
    maxArticles?: number;
    dateRange?: any;
    customDateRange?: any;
    scrapeLevel?: "list" | "detail" | "deep";
    categoryId?: string;
    sourceId?: string;
  } | null>(null);
  const [blockedDomain, setBlockedDomain] = useState<string>("");

  const {
    results,
    isScraping,
    isCancelling,
    currentResult,
    error,
    progress,
    scrapeUrl,
    deepScrape,
    cancelScrape,
    clearResults,
    setCurrentResult,
  } = useScrapeStore();

  const { scrapeSources, categories, syncFromBackend } = useSettingsStore();

  // 页面加载时同步配置数据
  useEffect(() => {
    syncFromBackend();
  }, [syncFromBackend]);

  // 默认选择第一个分类
  useEffect(() => {
    if (categories.length > 0 && !selectedCategory) {
      setSelectedCategory(categories[0].id);
    }
  }, [categories, selectedCategory]);

  // 加载最近执行记录
  useEffect(() => {
    const loadRecentHistory = async () => {
      setIsLoadingHistory(true);
      try {
        const res = await fetch("/api/scheduled/history?limit=5");
        if (res.ok) {
          const data = await res.json();
          setRecentHistory(data.histories || data || []);
        }
      } catch (error) {
        console.error("加载历史记录失败:", error);
      } finally {
        setIsLoadingHistory(false);
      }
    };
    loadRecentHistory();
  }, []);

  // 手动深度爬取完成后刷新持久化历史记录
  useEffect(() => {
    if (isScraping) return;
    fetch("/api/scheduled/history?limit=5")
      .then((res) => res.ok ? res.json() : [])
      .then((data) => setRecentHistory(data.histories || data || []))
      .catch((error) => console.error("刷新历史记录失败:", error));
  }, [isScraping]);

  // 选择已有来源时自动填充 URL
  const handleSelectSource = (source: ScrapeSource) => {
    setSelectedSource(source);
    setUrl(source.url);
    setShowSourceSelector(false);
  };

  // 跳转到设置页添加新来源
  const handleAddSource = () => {
    router.push("/settings/scrape");
  };

  const handleCreateSchedule = async () => {
    // 验证至少选择了一个来源或输入了自定义 URL
    if (selectedSources.length === 0 && !customUrlInput.trim()) {
      setScheduleMessage("请至少选择一个网站来源或输入自定义 URL。");
      return;
    }

    // 验证自定义 URL 格式
    if (customUrlInput.trim()) {
      try {
        const parsedUrl = new URL(customUrlInput.trim());
        if (!["http:", "https:"].includes(parsedUrl.protocol)) throw new Error("invalid protocol");
      } catch {
        setScheduleMessage("请输入有效的 http 或 https 网页地址。");
        return;
      }
    }

    setIsSavingSchedule(true);
    setScheduleMessage(null);
    try {
      // 构建任务名称
      const sourceNames = selectedSources.map(s => s.name);
      const customHostname = customUrlInput.trim() ? new URL(customUrlInput.trim()).hostname : "";
      const nameParts = [...sourceNames];
      if (customHostname) nameParts.push(customHostname);
      const taskName = nameParts.length > 2
        ? `${nameParts[0]} 等 ${nameParts.length} 个源 定时爬取`
        : `${nameParts.join("、")} 定时爬取`;

      // 创建定时任务
      const response = await fetch("/api/scheduled", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: taskName,
          sourceIds: selectedSources.map(s => s.id),
          customUrl: customUrlInput.trim() || undefined,
          scheduleTime,
          scrapeRange: scheduleRange,
          isEnabled: true,
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || result.detail || "创建定时任务失败");

      // 成功后重置状态并关闭对话框
      setScheduleDialogOpen(false);
      setSelectedSources([]);
      setCustomUrlInput("");
      setScheduleMessage(`定时任务已启用，将在每天 ${scheduleTime} 自动爬取 ${selectedSources.length + (customUrlInput.trim() ? 1 : 0)} 个源并保存到文档管理。`);

      // 刷新历史记录
      const historyRes = await fetch("/api/scheduled/history?limit=5");
      if (historyRes.ok) {
        const historyData = await historyRes.json();
        setRecentHistory(historyData.histories || historyData || []);
      }
    } catch (error) {
      setScheduleMessage(error instanceof Error ? error.message : "创建定时任务失败");
    } finally {
      setIsSavingSchedule(false);
    }
  };

  // 来源选择器内容（用于 Dialog）
  const SourceSelectorContent = () => (
    <div className="space-y-2">
      {scrapeSources.length === 0 ? (
        <div className="text-center py-6">
          <p className="text-muted-foreground mb-4">暂无已配置的网站来源</p>
          <Button onClick={handleAddSource} className="gap-2">
            <Settings className="h-4 w-4" />
            去配置网站
          </Button>
        </div>
      ) : (
        <>
          <ScrollArea className="max-h-[50vh]">
            <div className="space-y-2 pr-4">
              {scrapeSources
                .filter(s => s.isEnabled)
                .map((source) => (
                  <div
                    key={source.id}
                    className={cn(
                      "p-3 rounded-lg border cursor-pointer transition-all",
                      selectedSource?.id === source.id
                        ? "border-primary bg-primary/5"
                        : "hover:border-primary/50 hover:bg-muted/50"
                    )}
                    onClick={() => handleSelectSource(source)}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium truncate">{source.name}</span>
                          <Badge className={cn("text-xs shrink-0", getCategoryColors(source.category, categories))}>
                            {getCategoryLabel(source.category, categories)}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-1 text-sm text-muted-foreground">
                          <ExternalLink className="h-3 w-3 shrink-0" />
                          <span className="truncate">{source.url}</span>
                        </div>
                        {source.description && (
                          <p className="text-xs text-muted-foreground mt-1 line-clamp-1">
                            {source.description}
                          </p>
                        )}
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        className="gap-1 shrink-0"
                        onClick={(e) => {
                          e.stopPropagation();
                          setUrl(source.url);
                          setSelectedSource(source);
                          setShowSourceSelector(false);
                        }}
                      >
                        <Globe className="h-3 w-3" />
                        使用
                      </Button>
                    </div>
                  </div>
                ))}
            </div>
          </ScrollArea>

          <div className="flex items-center justify-between pt-2 border-t">
            <span className="text-sm text-muted-foreground">
              共 {scrapeSources.filter(s => s.isEnabled).length} 个已启用的网站
            </span>
            <Button variant="ghost" size="sm" onClick={handleAddSource} className="gap-1">
              <Settings className="h-3 w-3" />
              管理配置
            </Button>
          </div>
        </>
      )}
    </div>
  );

  // 页面加载时选择最新结果
  useEffect(() => {
    if (results.length > 0 && !currentResult) {
      setCurrentResult(results[0]);
    }
  }, [results, currentResult, setCurrentResult]);

  // 判断是否为文章详情页URL（而非列表页）
  const isArticleUrl = (urlStr: string): boolean => {
    // 文章页特征：URL 包含日期目录 + 文件名模式
    // 如 /202606/t20260618_xxx.shtml 或 /p/123456789
    const patterns = [
      /\/[0-9]{6}\/t\w+\.shtml?$/i,    // /202606/t20260618_xxx.shtml (中科院等政府网站)
      /\/P0\d+\.shtml?$/i,             // /P020250618123456789.shtml
      /\/info\/P0\d+\.shtml?$/i,       // /info/P020210615123456789.shtml
      /\/p\/\d+$/,                     // /p/123456789 (知乎等)
      /\/article\/\d+$/,               // /article/123456789 (CSDN博客等)
    ];
    return patterns.some(p => p.test(urlStr));
  };

  const handleScrape = async () => {
    if (!url.trim()) return;
    await scrapeUrl(url, advancedOptions);
  };

  const handleDeepScrape = async () => {
    if (!url.trim()) return;
    setExpandedCard(null); // 重置展开状态

    // 开始新爬取前清除旧结果，避免累积
    clearResults();

    // 智能选择爬取方式
    if (isArticleUrl(url)) {
      // 如果是文章详情页，直接单页爬取
      console.log('检测到文章详情页，使用单页爬取');
      await scrapeUrl(url, advancedOptions);
    } else {
      // 如果是列表页，使用深度爬取
      console.log('检测到列表页，使用深度爬取', { dateRange, scrapeLevel, selectedCategory, sourceId: selectedSource?.id });
      await deepScrape(
        url,
        maxArticles,
        dateRange?.preset,
        dateRange?.custom,
        advancedOptions,
        scrapeLevel,
        undefined,  // cookies
        selectedCategory,  // categoryId
        selectedSource?.id  // sourceId
      );
    }
  };

  const handleCopy = () => {
    if (currentResult?.content) {
      navigator.clipboard.writeText(currentResult.content);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "success":
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case "error":
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      case "cancelled":
        return <StopCircle className="h-4 w-4 text-orange-500" />;
      default:
        return <Loader2 className="h-4 w-4 text-yellow-500 animate-spin" />;
    }
  };

  const formatTime = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleString("zh-CN", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  };

  const toggleExpand = (cardUrl: string) => {
    setExpandedCard(expandedCard === cardUrl ? null : cardUrl);
  };

  // 导出单个结果为 Markdown 文件
  const exportAsFile = async (item: ScrapeResult) => {
    try {
      const res = await fetch("/api/scrape/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          articles: [item],
          format: "markdown",
        }),
      });

      if (!res.ok) throw new Error("导出失败");

      const data = await res.json();
      await saveFileWithPicker(data.filename, data.content);
    } catch (err) {
      console.error("导出失败:", err);
    }
  };

  // 使用 File System Access API 让用户选择保存位置
  const saveFileWithPicker = async (filename: string, content: string) => {
    // 检查是否支持 File System Access API
    if ('showSaveFilePicker' in window) {
      try {
        const handle = await (window as any).showSaveFilePicker({
          suggestedName: filename,
          types: [
            {
              description: 'Markdown 文件',
              accept: { 'text/markdown': ['.md'] },
            },
            {
              description: '所有文件',
              accept: { '*/*': ['.*'] },
            },
          ],
        });
        const writable = await handle.createWritable();
        await writable.write(content);
        await writable.close();
        return true;
      } catch (err) {
        // 用户取消了选择
        if ((err as Error).name === 'AbortError') {
          return false;
        }
        // 如果 API 出错，尝试使用传统方式
        console.warn('File System Access API 失败，使用传统方式:', err);
      }
    }

    // 回退：使用传统方式下载
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    return true;
  };

  // 批量导出所有结果到本地
  const exportAllResults = async () => {
    setIsExporting(true);
    setExportSuccess(null);

    try {
      const res = await fetch("/api/scrape/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          articles: results.map(r => ({
            title: r.title,
            url: r.url,
            author: r.author,
            published_at: r.publishedAt,
            style: r.style,
            keywords: r.keywords,
            summary: r.summary,
            content: r.content,
            word_count: r.wordCount,
          })),
          format: "markdown",
        }),
      });

      if (!res.ok) throw new Error("导出失败");

      const data = await res.json();
      await saveFileWithPicker(data.filename, data.content);
      setExportSuccess(`已导出 ${results.length} 篇文章`);
    } catch (err) {
      setExportSuccess("导出失败: " + (err instanceof Error ? err.message : "未知错误"));
    }

    setIsExporting(false);
    setTimeout(() => setExportSuccess(null), 3000);
  };

  // 保存所有结果到数据库（使用批量 API）
  const saveAllToDatabase = async () => {
    console.log("保存到数据库开始...", { resultsCount: results.length });
    setIsExporting(true);
    setExportSuccess(null);

    try {
      const res = await fetch("/api/scrape/save-batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          articles: results.map(r => ({
            title: r.title,
            url: r.url,
            author: r.author,
            published_at: r.publishedAt,
            style: r.style,
            keywords: r.keywords,
            summary: r.summary,
            content: r.content,
            word_count: r.wordCount,
            html: r.html,
            source_id: selectedSource?.id,
          })),
          category_id: selectedCategory,
        }),
      });

      const data = await res.json();
      console.log("保存结果:", data);

      if (data.success) {
        setExportSuccess(data.message);
      } else {
        setExportSuccess(`保存失败: ${data.error || data.message}`);
      }
    } catch (err) {
      console.error("保存出错:", err);
      setExportSuccess("保存失败: " + (err instanceof Error ? err.message : "未知错误"));
    }

    setIsExporting(false);
    setTimeout(() => setExportSuccess(null), 5000);
  };

  // 切换选择状态（用于批量导出）
  const toggleSelectForExport = (itemUrl: string) => {
    setSelectedForExport(prev => {
      const next = new Set(prev);
      if (next.has(itemUrl)) {
        next.delete(itemUrl);
      } else {
        next.add(itemUrl);
      }
      return next;
    });
  };

  // 全选/取消全选
  const toggleSelectAll = () => {
    if (selectedForExport.size === results.length) {
      setSelectedForExport(new Set());
    } else {
      setSelectedForExport(new Set(results.map(r => `${r.url}-${r.scrapedAt}`)));
    }
  };

  // 导出选中的结果到本地
  const exportSelected = async () => {
    const selectedItems = results.filter(item =>
      selectedForExport.has(`${item.url}-${item.scrapedAt}`)
    );

    setIsExporting(true);
    setExportSuccess(null);

    try {
      const res = await fetch("/api/scrape/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          articles: selectedItems.map(r => ({
            title: r.title,
            url: r.url,
            author: r.author,
            published_at: r.publishedAt,
            style: r.style,
            keywords: r.keywords,
            summary: r.summary,
            content: r.content,
            word_count: r.wordCount,
          })),
          format: "markdown",
        }),
      });

      if (!res.ok) throw new Error("导出失败");

      const data = await res.json();
      await saveFileWithPicker(data.filename, data.content);
      setExportSuccess(`已导出 ${selectedItems.length} 篇文章`);
    } catch (err) {
      setExportSuccess("导出失败: " + (err instanceof Error ? err.message : "未知错误"));
    }

    setIsExporting(false);
    setTimeout(() => setExportSuccess(null), 3000);
  };

  // 保存选中的结果到数据库（使用批量 API）
  const saveSelectedToDatabase = async () => {
    const selectedItems = results.filter(item =>
      selectedForExport.has(`${item.url}-${item.scrapedAt}`)
    );

    setIsExporting(true);
    setExportSuccess(null);

    try {
      const res = await fetch("/api/scrape/save-batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          articles: selectedItems.map(r => ({
            title: r.title,
            url: r.url,
            author: r.author,
            published_at: r.publishedAt,
            style: r.style,
            keywords: r.keywords,
            summary: r.summary,
            content: r.content,
            word_count: r.wordCount,
            html: r.html,
            source_id: selectedSource?.id,
          })),
          category_id: selectedCategory,
        }),
      });

      const data = await res.json();

      if (data.success) {
        setExportSuccess(data.message);
      } else {
        setExportSuccess(`保存失败: ${data.error || data.message}`);
      }
    } catch (err) {
      setExportSuccess("保存失败: " + (err instanceof Error ? err.message : "未知错误"));
    }

    setIsExporting(false);
    setTimeout(() => setExportSuccess(null), 5000);
  };

  // 打开 Cookie 输入对话框
  const openCookieDialog = (domain: string, params: {
    url: string;
    isDeepScrape: boolean;
    options?: any;
    maxArticles?: number;
    dateRange?: any;
    customDateRange?: any;
    scrapeLevel?: "list" | "detail" | "deep";
    categoryId?: string;
    sourceId?: string;
  }) => {
    setBlockedDomain(domain);
    setPendingScrapeParams(params);
    setCookieInput("");
    setShowCookieDialog(true);
  };

  // 使用 Cookie 重新爬取
  const retryWithCookie = async () => {
    if (!pendingScrapeParams || !cookieInput.trim()) return;

    setShowCookieDialog(false);

    if (pendingScrapeParams.isDeepScrape) {
      await deepScrape(
        pendingScrapeParams.url,
        pendingScrapeParams.maxArticles,
        pendingScrapeParams.dateRange,
        pendingScrapeParams.customDateRange,
        pendingScrapeParams.options,
        pendingScrapeParams.scrapeLevel,
        cookieInput.trim(),
        pendingScrapeParams.categoryId,
        pendingScrapeParams.sourceId
      );
    } else {
      // 单页爬取
      const { scrapeUrl } = useScrapeStore.getState();
      await scrapeUrl(pendingScrapeParams.url, pendingScrapeParams.options, cookieInput.trim());
    }
  };

  // 渲染 Cookie 输入对话框
  const renderCookieDialog = () => (
    <Dialog open={showCookieDialog} onOpenChange={setShowCookieDialog}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-orange-500" />
            网站需要 Cookie 才能访问
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <p className="text-sm text-muted-foreground">
            网站 <span className="font-medium text-foreground">{blockedDomain}</span> 检测到异常访问，
            需要输入 Cookie 才能继续爬取。
          </p>

          <div className="space-y-2">
            <Label htmlFor="cookie-input">Cookie</Label>
            <textarea
              id="cookie-input"
              value={cookieInput}
              onChange={(e) => setCookieInput(e.target.value)}
              placeholder="粘贴从浏览器开发者工具获取的 Cookie..."
              className="w-full h-32 px-3 py-2 text-sm rounded-md border border-input bg-background resize-none focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <p className="text-xs text-muted-foreground">
              获取方法：打开 {blockedDomain} → 登录 → 按 F12 打开开发者工具 → Network → 刷新页面 → 点击任意请求 → 复制 Request Headers 中的 Cookie
            </p>
          </div>

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setShowCookieDialog(false)}>
              取消
            </Button>
            <Button onClick={retryWithCookie} disabled={!cookieInput.trim()}>
              用 Cookie 重新爬取
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );

  // 渲染单个文章卡片
  const renderArticleCard = (item: ScrapeResult, isSelected: boolean) => {
    const itemKey = `${item.url}-${item.scrapedAt}`;
    const isChecked = selectedForExport.has(itemKey);

    return (
    <Card
      key={itemKey}
      className={cn(
        "transition-all cursor-pointer hover:shadow-md",
        isSelected && "ring-2 ring-primary",
        isChecked && "border-primary bg-primary/5"
      )}
      onClick={() => setCurrentResult(item)}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start gap-2">
          {/* 复选框（不阻止冒泡） */}
          <Checkbox
            checked={isChecked}
            onCheckedChange={() => toggleSelectForExport(itemKey)}
            onClick={(e) => e.stopPropagation()}
            className="mt-1 shrink-0"
          />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              {getStatusIcon(item.status)}
              <CardTitle className="text-base font-semibold line-clamp-2">
                {item.title || "无标题"}
              </CardTitle>
            </div>
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-primary hover:underline flex items-center gap-1"
              onClick={(e) => e.stopPropagation()}
            >
              <Link2 className="h-3 w-3" />
              <span className="truncate">{item.url}</span>
            </a>
          </div>
          <Badge variant="secondary" className="text-xs shrink-0">
            {item.wordCount.toLocaleString()} 字
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {/* 文章元信息 + 文体标签 */}
        <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          {/* 文体标签（突出显示） */}
          {item.style && (
            <Badge variant="secondary" className="text-xs bg-violet-100 text-violet-700 dark:bg-violet-900 dark:text-violet-300">
              {item.style}
            </Badge>
          )}
          {item.author && (
            <div className="flex items-center gap-1">
              <User className="h-3 w-3" />
              <span>{item.author}</span>
            </div>
          )}
          {item.publishedAt && (
            <div className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              <span>{item.publishedAt}</span>
            </div>
          )}
          <div className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            <span>{formatTime(item.scrapedAt)}</span>
          </div>
        </div>

        {/* 摘要 */}
        {item.summary && (
          <p className="text-sm text-muted-foreground line-clamp-2">
            {item.summary}
          </p>
        )}

        {/* 关键词标签 */}
        {item.keywords && item.keywords.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {item.keywords.slice(0, 5).map((keyword, index) => (
              <Badge key={index} variant="outline" className="text-xs">
                <Tag className="h-2 w-2 mr-1" />
                {keyword}
              </Badge>
            ))}
            {item.keywords.length > 5 && (
              <Badge variant="outline" className="text-xs">
                +{item.keywords.length - 5}
              </Badge>
            )}
          </div>
        )}

        <Separator />

        {/* 操作按钮 */}
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="gap-1"
            onClick={(e) => {
              e.stopPropagation();
              toggleExpand(item.url);
            }}
          >
            {expandedCard === item.url ? (
              <>
                <EyeOff className="h-3 w-3" />
                收起
              </>
            ) : (
              <>
                <AlignLeft className="h-3 w-3" />
                摘要及原文
              </>
            )}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="gap-1"
            onClick={async (e) => {
              e.stopPropagation();
              try {
                await navigator.clipboard.writeText(item.content || "");
              } catch (err) {
                console.error("复制失败:", err);
                // fallback: 创建临时 textarea
                const textarea = document.createElement("textarea");
                textarea.value = item.content || "";
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand("copy");
                document.body.removeChild(textarea);
              }
            }}
          >
            <Copy className="h-3 w-3" />
            复制
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="gap-1"
            onClick={(e) => {
              e.stopPropagation();
              exportAsFile(item);
            }}
          >
            <FileDown className="h-3 w-3" />
            导出
          </Button>
        </div>

        {/* 展开的原文内容 */}
        {expandedCard === item.url && (
          <div className="mt-2 p-3 bg-muted/50 rounded-lg">
            <div className="text-xs max-h-96 overflow-y-auto">
              {/* 元信息和标题 */}
              <div className="mb-3 pb-2 border-b">
                <h3 className="text-base font-semibold mb-2">{item.title || "无标题"}</h3>
                <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                  <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline flex items-center gap-1">
                    <Link2 className="h-3 w-3" />
                    {item.url}
                  </a>
                  {item.author && (
                    <span className="flex items-center gap-1">
                      <User className="h-3 w-3" />
                      {item.author}
                    </span>
                  )}
                  {item.publishedAt && (
                    <span className="flex items-center gap-1">
                      <Calendar className="h-3 w-3" />
                      {item.publishedAt}
                    </span>
                  )}
                </div>
              </div>

              {/* 原文正文 */}
              <div className="whitespace-pre-wrap text-sm leading-relaxed">
                {item.content || "未获取到内容"}
              </div>
            </div>
          </div>
        )}

        {/* 错误信息或反爬提示 */}
        {(item.status === "error" || item.status === "anti_bot_blocked") && item.errorMessage && (
          <div className="p-3 rounded text-sm space-y-2">
            {item.status === "anti_bot_blocked" ? (
              <div className="bg-orange-500/10 text-orange-600 border border-orange-500/20 rounded p-3">
                <div className="flex items-center gap-2 mb-2">
                  <AlertCircle className="h-4 w-4" />
                  <span className="font-medium">网站有反爬保护</span>
                </div>
                <p className="text-sm mb-2">{item.errorMessage}</p>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={(e) => {
                    e.stopPropagation();
                    // 判断是否为列表页（需要深度爬取）
                    const isListPage = !isArticleUrl(item.url);
                    openCookieDialog(item.blockedDomain || "", {
                      url: item.url,
                      isDeepScrape: isListPage,
                      maxArticles: maxArticles,
                      dateRange: dateRange?.preset,
                      customDateRange: dateRange?.custom,
                      scrapeLevel: scrapeLevel,
                      categoryId: selectedCategory,
                      sourceId: selectedSource?.id,
                    });
                  }}
                >
                  输入 Cookie 继续
                </Button>
              </div>
            ) : (
              <div className="bg-destructive/10 text-destructive rounded p-2">
                {item.errorMessage}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
    );
  };

  return (
    <div className="flex h-full">
      {/* 左侧文章列表 */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="p-6 border-b border-border">
          <div className="max-w-4xl mx-auto">
            <h1 className="text-2xl font-semibold mb-4">智能网页爬取</h1>
            <p className="text-muted-foreground mb-6">
              输入列表页 URL，自动识别并爬取所有文章，提取标题、作者、时间、摘要和关键字
            </p>

            {/* URL 输入 */}
            <Card className="p-4">
              <div className="space-y-4">
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Globe className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      value={url}
                      onChange={(e) => {
                        setUrl(e.target.value);
                        setSelectedSource(null);
                      }}
                      placeholder="输入列表页 URL，例如：https://news.ycombinator.com"
                      className="pl-9"
                      onKeyDown={(e) => e.key === "Enter" && !isScraping && handleDeepScrape()}
                      disabled={isScraping}
                    />
                  </div>
                  {/* 分类选择（从后端网页配置动态加载） */}
                    <Select
                      value={selectedCategory}
                      onValueChange={(value) => value && setSelectedCategory(value as string)}
                      disabled={isScraping}
                    >
                      <SelectTrigger className="w-[140px] gap-1">
                        <Tag className="h-4 w-4 text-muted-foreground shrink-0" />
                        <SelectValue placeholder="选择分类" />
                      </SelectTrigger>
                      <SelectContent>
                        {categories.length === 0 ? (
                          <div className="px-2 py-1.5 text-sm text-muted-foreground">
                            暂无分类
                          </div>
                        ) : (
                          categories.map((cat) => (
                            <SelectItem key={cat.id} value={cat.id}>
                              <span className="flex items-center gap-2">
                                <span
                                  className="inline-block h-2 w-2 rounded-full"
                                  style={{ backgroundColor: cat.color }}
                                />
                                {cat.name}
                              </span>
                            </SelectItem>
                          ))
                        )}
                      </SelectContent>
                    </Select>

                    <Button
                      variant="outline"
                      onClick={() => setShowSourceSelector(true)}
                      className="gap-1"
                      disabled={isScraping}
                    >
                      <Bookmark className="h-4 w-4" />
                      {scrapeSources.filter(s => s.isEnabled).length > 0 && (
                        <Badge variant="secondary" className="ml-1">
                          {scrapeSources.filter(s => s.isEnabled).length}
                        </Badge>
                      )}
                      已配置
                    </Button>

                    {/* 来源选择器 Dialog */}
                    <Dialog open={showSourceSelector} onOpenChange={setShowSourceSelector}>
                      <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
                        <DialogHeader>
                          <DialogTitle>选择已配置的网站</DialogTitle>
                        </DialogHeader>
                        <SourceSelectorContent />
                        <div className="flex justify-end pt-2">
                          <Button variant="outline" onClick={() => setShowSourceSelector(false)}>
                            关闭
                          </Button>
                        </div>
                      </DialogContent>
                    </Dialog>
                  <Button
                    variant="outline"
                    onClick={() => { setScheduleMessage(null); setScheduleDialogOpen(true); }}
                    disabled={!url.trim() || isScraping}
                    className="gap-2"
                  >
                    <Clock className="h-4 w-4" />
                    定时爬取
                  </Button>
                  {isScraping ? (
                    <Button
                      onClick={cancelScrape}
                      disabled={isCancelling}
                      variant="destructive"
                      className="gap-2"
                    >
                      {isCancelling ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          正在停止...
                        </>
                      ) : (
                        <>
                          <StopCircle className="h-4 w-4" />
                          停止爬取
                        </>
                      )}
                    </Button>
                  ) : (
                    <Button
                      onClick={handleDeepScrape}
                      disabled={!url.trim()}
                      className="gap-2"
                    >
                      <Sparkles className="h-4 w-4" />
                      智能爬取
                    </Button>
                  )}
                </div>

                {scheduleMessage && !scheduleDialogOpen && (
                  <div className="flex flex-col gap-2 rounded-md border border-emerald-500/25 bg-emerald-500/5 px-3 py-2 text-sm sm:flex-row sm:items-center sm:justify-between">
                    <span>{scheduleMessage}</span>
                    <div className="flex shrink-0 gap-2">
                      <Button variant="ghost" size="sm" onClick={() => router.push("/settings/scrape?tab=scheduled")}>管理定时任务</Button>
                      <Button variant="ghost" size="sm" onClick={() => router.push("/articles")}>文档管理</Button>
                    </div>
                  </div>
                )}

                {/* 最近执行记录 */}
                {recentHistory.length > 0 && (
                  <Card className="mt-4">
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-sm font-medium flex items-center gap-2">
                          <History className="h-4 w-4" />
                          最近执行记录
                        </CardTitle>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-xs"
                          onClick={() => router.push("/settings/scrape?tab=scheduled")}
                        >
                          查看全部
                        </Button>
                      </div>
                    </CardHeader>
                    <CardContent className="pt-0">
                      <div className="space-y-2">
                        {recentHistory.slice(0, 3).map((item, index) => (
                          <div
                            key={item.id || index}
                            className="flex items-center gap-3 p-2 rounded-lg bg-muted/30"
                          >
                            {item.status === "success" ? (
                              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                            ) : item.status === "failed" ? (
                              <AlertCircle className="h-4 w-4 text-destructive shrink-0" />
                            ) : (
                              <Loader2 className="h-4 w-4 text-muted-foreground shrink-0 animate-spin" />
                            )}
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium truncate">
                                {item.taskName || item.articleTitle || "手动爬取"}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                {item.status === "success"
                                  ? `成功爬取 ${item.articlesCount || 0} 篇文章`
                                  : item.status === "failed"
                                    ? `失败: ${item.errorMessage || "未知错误"}`
                                    : "正在执行中..."}
                              </p>
                            </div>
                            <span className="text-xs text-muted-foreground shrink-0">
                              {item.startedAt
                                ? new Date(item.startedAt).toLocaleString("zh-CN", {
                                  month: "2-digit",
                                  day: "2-digit",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })
                                : ""}
                            </span>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}

                <Dialog open={scheduleDialogOpen} onOpenChange={setScheduleDialogOpen}>
                  <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
                    <DialogHeader>
                      <DialogTitle className="flex items-center gap-2"><Clock className="h-5 w-5" />设置网页定时爬取</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-5 py-2">
                      {/* 执行时间设置 */}
                      <div className="grid gap-4 sm:grid-cols-2">
                        <div className="space-y-2">
                          <Label htmlFor="webScheduleTime">每天执行时间</Label>
                          <Input id="webScheduleTime" type="time" value={scheduleTime} onChange={(event) => setScheduleTime(event.target.value)} />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="webScheduleRange">每次回溯范围</Label>
                          <select id="webScheduleRange" value={scheduleRange} onChange={(event) => setScheduleRange(event.target.value as "1d" | "7d" | "30d")} className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm">
                            <option value="1d">最近 1 天</option>
                            <option value="7d">最近 7 天</option>
                            <option value="30d">最近 30 天</option>
                          </select>
                        </div>
                      </div>

                      {/* 已配置网站来源多选 */}
                      <div className="space-y-2">
                        <Label>选择网站来源 {selectedSources.length > 0 && <span className="text-primary">（已选 {selectedSources.length} 个）</span>}</Label>
                        <ScrollArea className="h-[200px] rounded-md border p-3">
                          {scrapeSources.filter(s => s.isEnabled).length === 0 ? (
                            <div className="text-center py-6 text-muted-foreground">
                              <p className="mb-2">暂无已配置的网站来源</p>
                              <Button variant="outline" size="sm" onClick={handleAddSource}>
                                <Settings className="mr-2 h-4 w-4" />去配置网站
                              </Button>
                            </div>
                          ) : (
                            <div className="space-y-2">
                              {scrapeSources.filter(s => s.isEnabled).map((source) => (
                                <div
                                  key={source.id}
                                  className={cn(
                                    "flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-all",
                                    selectedSources.some(s => s.id === source.id)
                                      ? "bg-primary/10 border border-primary/30"
                                      : "hover:bg-muted/50 border border-transparent"
                                  )}
                                  onClick={() => {
                                    setSelectedSources(prev =>
                                      prev.some(s => s.id === source.id)
                                        ? prev.filter(s => s.id !== source.id)
                                        : [...prev, source]
                                    );
                                  }}
                                >
                                  <Checkbox
                                    checked={selectedSources.some(s => s.id === source.id)}
                                    onCheckedChange={(checked) => {
                                      setSelectedSources(prev =>
                                        checked
                                          ? [...prev, source]
                                          : prev.filter(s => s.id !== source.id)
                                      );
                                    }}
                                  />
                                  <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2">
                                      <span className="font-medium text-sm">{source.name}</span>
                                      <Badge className={cn("text-xs", getCategoryColors(source.category, categories))}>
                                        {getCategoryLabel(source.category, categories)}
                                      </Badge>
                                    </div>
                                    <p className="text-xs text-muted-foreground truncate">{source.url}</p>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </ScrollArea>
                      </div>

                      {/* 自定义 URL 输入 */}
                      <div className="space-y-2">
                        <Label htmlFor="customUrl">自定义 URL（可选）</Label>
                        <div className="flex gap-2">
                          <Input
                            id="customUrl"
                            value={customUrlInput}
                            onChange={(e) => setCustomUrlInput(e.target.value)}
                            placeholder="https://example.com"
                          />
                        </div>
                      </div>

                      {/* 提示信息 */}
                      <div className="rounded-md border border-primary/20 bg-primary/5 px-3 py-2 text-sm leading-6 text-muted-foreground">
                        任务创建后立即启用。每次定时爬取会自动去重并保存到"文档管理"；已配置来源沿用其分类，自定义 URL 保存为未分类。
                      </div>

                      {scheduleMessage && <p className="text-sm text-destructive">{scheduleMessage}</p>}

                      {/* 操作按钮 */}
                      <div className="flex justify-end gap-2">
                        <Button variant="outline" onClick={() => setScheduleDialogOpen(false)}>取消</Button>
                        <Button
                          onClick={handleCreateSchedule}
                          disabled={isSavingSchedule || !scheduleTime || (selectedSources.length === 0 && !customUrlInput.trim())}
                        >
                          {isSavingSchedule && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                          创建并启用
                        </Button>
                      </div>
                    </div>
                  </DialogContent>
                </Dialog>

                {/* 已选来源提示 */}
                {selectedSource && (
                  <div className="flex items-center gap-2 p-2 bg-primary/5 border border-primary/20 rounded-lg">
                    <Bookmark className="h-4 w-4 text-primary shrink-0" />
                    <span className="text-sm">
                      已选择: <span className="font-medium">{selectedSource.name}</span>
                    </span>
                    <Badge className={cn("text-xs shrink-0", getCategoryColors(selectedSource.category, categories))}>
                      {getCategoryLabel(selectedSource.category, categories)}
                    </Badge>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="ml-auto h-6 px-2"
                      onClick={() => {
                        setSelectedSource(null);
                        setUrl("");
                      }}
                    >
                      清除
                    </Button>
                  </div>
                )}

                {/* 来源选择器已改为 Dialog 模式 */}

                {/* 深度爬取选项 */}
                <div className="flex items-center gap-4 p-3 bg-primary/10 rounded-lg">
                  <div className="flex items-center gap-2">
                    <Layers className="h-4 w-4 text-primary" />
                    <span className="text-sm">自动识别文章链接并爬取</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Label className="text-sm">爬取级别</Label>
                    <select
                      value={scrapeLevel}
                      onChange={(e) => setScrapeLevel(e.target.value as ScrapeLevel)}
                      className="h-8 px-2 rounded-md border border-input bg-background text-sm"
                    >
                      <option value="list">仅提取链接</option>
                      <option value="detail">详情页（一级）</option>
                      <option value="deep">深度爬取（多级）</option>
                    </select>
                  </div>
                  <div className="flex items-center gap-2">
                    <Label className="text-sm">最多</Label>
                    <select
                      value={maxArticles}
                      onChange={(e) => setMaxArticles(parseInt(e.target.value))}
                      className="h-8 px-2 rounded-md border border-input bg-background text-sm"
                    >
                      <option value={5}>5 篇</option>
                      <option value={10}>10 篇</option>
                      <option value={20}>20 篇</option>
                      <option value={30}>30 篇</option>
                    </select>
                  </div>
                </div>

                {/* 时间范围选择 */}
                <Card className="p-4">
                  <DateRangeSelector
                    value={dateRange}
                    onChange={setDateRange}
                    disabled={isScraping}
                  />
                </Card>

                {/* 高级选项 */}
                <div>
                  <button
                    onClick={() => setShowAdvanced(!showAdvanced)}
                    className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <Link2 className="h-3.5 w-3.5" />
                    高级选项
                    {showAdvanced ? (
                      <ChevronUp className="h-3.5 w-3.5" />
                    ) : (
                      <ChevronDown className="h-3.5 w-3.5" />
                    )}
                  </button>

                  {showAdvanced && (
                    <div className="mt-4 p-4 bg-muted/50 rounded-lg space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="flex items-center space-x-2">
                          <Checkbox
                            id="extract-content"
                            checked={advancedOptions.extractContent}
                            onCheckedChange={(checked) =>
                              setAdvancedOptions({
                                ...advancedOptions,
                                extractContent: checked as boolean,
                              })
                            }
                          />
                          <Label htmlFor="extract-content" className="text-sm cursor-pointer">
                            提取正文内容
                          </Label>
                        </div>
                        <div className="flex items-center space-x-2">
                          <Checkbox
                            id="fetch-html"
                            checked={advancedOptions.fetchHtml}
                            onCheckedChange={(checked) =>
                              setAdvancedOptions({
                                ...advancedOptions,
                                fetchHtml: checked as boolean,
                              })
                            }
                          />
                          <Label htmlFor="fetch-html" className="text-sm cursor-pointer">
                            获取原始 HTML
                          </Label>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label className="text-sm">超时时间</Label>
                          <select
                            value={advancedOptions.timeout}
                            onChange={(e) =>
                              setAdvancedOptions({
                                ...advancedOptions,
                                timeout: parseInt(e.target.value),
                              })
                            }
                            className="w-full h-9 px-3 rounded-md border border-input bg-background text-sm"
                          >
                            <option value={10}>10 秒</option>
                            <option value={30}>30 秒</option>
                            <option value={60}>60 秒</option>
                            <option value={120}>120 秒</option>
                          </select>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </Card>

            {/* 错误提示 */}
            {error && (
              <Card className="mt-4 p-4 border-destructive">
                <div className="flex items-center gap-2 text-destructive">
                  <AlertCircle className="h-4 w-4" />
                  <span>{error}</span>
                </div>
              </Card>
            )}
          </div>
        </div>

        {/* 文章列表 */}
        <ScrollArea className="flex-1">
          <div className="p-6 max-w-4xl mx-auto">
            {/* 加载状态 */}
            {isScraping && (
              <Card className="p-8">
                <div className="flex flex-col items-center text-center">
                  <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
                  <p className="text-lg font-medium mb-2">
                    {progress?.stageName || "正在智能识别并爬取文章..."}
                  </p>

                  {/* 阶段详情 */}
                  {progress?.stageDetail && (
                    <p className="text-sm text-muted-foreground mb-4">{progress.stageDetail}</p>
                  )}

                  {/* 进度显示 */}
                  {progress && progress.total > 1 && (
                    <div className="w-full max-w-md mt-4">
                      <div className="flex items-center justify-between text-sm text-muted-foreground mb-2">
                        <span>爬取进度</span>
                        <span>{progress.current} / {progress.total}</span>
                      </div>
                      {/* 进度条 */}
                      <div className="w-full bg-muted rounded-full h-2 mb-2">
                        <div
                          className="bg-primary h-2 rounded-full transition-all duration-300"
                          style={{ width: `${(progress.current / progress.total) * 100}%` }}
                        />
                      </div>
                      {/* 当前正在爬取的文章 */}
                      {progress.currentTitle && (
                        <p className="text-xs text-muted-foreground truncate mt-2">
                          正在爬取: <span className="text-foreground">{progress.currentTitle}</span>
                        </p>
                      )}
                    </div>
                  )}

                  {/* 阶段流程指示 */}
                  <div className="flex items-center gap-2 mt-6 flex-wrap justify-center">
                    <span className={cn(
                      "px-2 py-1 rounded text-xs",
                      progress?.stage === 1 ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                    )}>
                      1. 解析列表页
                    </span>
                    <span className="text-muted-foreground">→</span>
                    <span className={cn(
                      "px-2 py-1 rounded text-xs",
                      progress?.stage === 2 ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                    )}>
                      2. 识别链接
                    </span>
                    <span className="text-muted-foreground">→</span>
                    <span className={cn(
                      "px-2 py-1 rounded text-xs",
                      progress?.stage === 3 ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                    )}>
                      3. 爬取内容
                    </span>
                    <span className="text-muted-foreground">→</span>
                    <span className="text-xs text-muted-foreground px-2 py-1">完成</span>
                  </div>
                </div>
              </Card>
            )}

            {/* 文章卡片列表 */}
            {!isScraping && results.length > 0 && (
              <div className="space-y-4">
                {/* 批量操作栏 - 简化版：只有导出到本地和保存到数据库两种方式 */}
                <div className="flex items-center justify-between flex-wrap gap-3 p-4 bg-muted/50 rounded-lg">
                  <div className="flex items-center gap-3">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={toggleSelectAll}
                      className="gap-2"
                    >
                      <Checkbox
                        checked={selectedForExport.size === results.length && results.length > 0}
                        className="h-4 w-4"
                      />
                      {selectedForExport.size === results.length ? "取消全选" : "全选"}
                    </Button>
                    <span className="text-sm text-muted-foreground">
                      已选择 {selectedForExport.size} / {results.length} 篇
                    </span>
                  </div>

                  {/* 分类选择（用于保存到数据库） */}
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">保存分类:</span>
                    <select
                      value={selectedCategory}
                      onChange={(e) => setSelectedCategory(e.target.value)}
                      className="h-8 px-2 rounded-md border border-input bg-background text-sm min-w-[100px]"
                    >
                      {categories.map((cat: any) => (
                        <option key={cat.id} value={cat.id}>{cat.name}</option>
                      ))}
                    </select>
                  </div>

                  {/* 导出操作按钮 */}
                  <div className="flex items-center gap-2">
                    {/* 导出到本地 */}
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-2"
                      onClick={selectedForExport.size > 0 ? exportSelected : exportAllResults}
                      disabled={isExporting}
                    >
                      <FileDown className="h-4 w-4" />
                      导出到本地
                    </Button>

                    {/* 保存到数据库 */}
                    <Button
                      variant="default"
                      size="sm"
                      className="gap-2"
                      onClick={selectedForExport.size > 0 ? saveSelectedToDatabase : saveAllToDatabase}
                      disabled={isExporting}
                    >
                      <Download className="h-4 w-4" />
                      保存到数据库
                    </Button>
                  </div>
                </div>

                {/* 文章卡片 */}
                {results.map((item) => renderArticleCard(item, currentResult === item))}

                {/* 导出成功提示 */}
                {exportSuccess && (
                  <Card className="p-4 border-green-500 bg-green-50 dark:bg-green-900/20">
                    <div className="flex items-center gap-2 text-green-600">
                      <CheckCircle2 className="h-5 w-5" />
                      <span>{exportSuccess}</span>
                    </div>
                  </Card>
                )}

                {/* 导出中提示 */}
                {isExporting && (
                  <Card className="p-4">
                    <div className="flex items-center gap-2">
                      <Loader2 className="h-5 w-5 animate-spin text-primary" />
                      <span>正在处理...</span>
                    </div>
                  </Card>
                )}
              </div>
            )}

            {/* 空状态 */}
            {!isScraping && results.length === 0 && (
              <Card className="p-8 text-center">
                <div className="w-16 h-16 rounded-full bg-muted mx-auto flex items-center justify-center mb-4">
                  <Globe className="h-8 w-8 text-muted-foreground" />
                </div>
                <h3 className="text-lg font-medium mb-2">输入列表页 URL 开始智能爬取</h3>
                <p className="text-muted-foreground text-sm">
                  支持爬取新闻列表、博客列表等，自动识别所有文章链接并爬取正文内容
                </p>
              </Card>
            )}
          </div>
        </ScrollArea>
      </div>

      {/* 右侧历史记录 */}
      <div className="w-72 border-l border-border flex flex-col bg-card/50">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h3 className="font-semibold flex items-center gap-2">
            <History className="h-4 w-4" />
            历史记录
          </h3>
          {results.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={clearResults}
              className="text-muted-foreground hover:text-destructive"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
        </div>

        <ScrollArea className="flex-1">
          {results.length === 0 ? (
            <div className="p-4 text-center text-sm text-muted-foreground">
              暂无爬取记录
            </div>
          ) : (
            <div className="p-2 space-y-1">
              {results.map((item, index) => (
                <button
                  key={`${item.url}-${item.scrapedAt}-${index}`}
                  onClick={() => setCurrentResult(item)}
                  className={cn(
                    "w-full text-left p-3 rounded-lg hover:bg-accent transition-colors",
                    currentResult === item && "bg-accent"
                  )}
                >
                  <div className="flex items-start gap-2">
                    {getStatusIcon(item.status)}
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm truncate">
                        {item.title || "无标题"}
                      </p>
                      <p className="text-xs text-muted-foreground truncate mt-1">
                        {item.url}
                      </p>
                      <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatTime(item.scrapedAt)}
                        </span>
                        <span>·</span>
                        <span>{item.wordCount.toLocaleString()} 字</span>
                      </div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </ScrollArea>
      </div>

      {/* Cookie 输入对话框 */}
      {renderCookieDialog()}
    </div>
  );
}
