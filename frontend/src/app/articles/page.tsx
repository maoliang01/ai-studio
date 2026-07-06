"use client";

import { useState, useEffect } from "react";
import type { Article, ArticleStats } from "@/types";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuTrigger,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2, Search, Trash2, Eye, ChevronLeft, ChevronRight, RefreshCw, Database, Filter, X, FileText, Download, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

// 格式化数字
function formatNumber(num: number | undefined | null): string {
  if (num == null || isNaN(num)) return "0";
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + "w";
  }
  return num.toLocaleString();
}

// 格式化日期
function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return "-";
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

export default function ArticlesPage() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [stats, setStats] = useState<ArticleStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [selectedArticle, setSelectedArticle] = useState<Article | null>(null);
  const [dbConnected, setDbConnected] = useState(false);
  const [checkingDb, setCheckingDb] = useState(true);

  // 筛选条件
  const [categoryFilter, setCategoryFilter] = useState<string>("");
  const [styleFilter, setStyleFilter] = useState<string>("");
  const [availableStyles, setAvailableStyles] = useState<Array<{name: string, count: number}>>([]);

  // 复选相关状态
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchDeleteDialogOpen, setBatchDeleteDialogOpen] = useState(false);
  const [isBatchDeleting, setIsBatchDeleting] = useState(false);

  // 复选辅助
  const allSelected = articles.length > 0 && selectedIds.size === articles.length;
  const someSelected = selectedIds.size > 0 && selectedIds.size < articles.length;

  // 全选/取消全选
  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(new Set(articles.map(a => a.id)));
    } else {
      setSelectedIds(new Set());
    }
  };

  // 切换单条选中
  const handleSelectOne = (id: string, checked: boolean) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (checked) {
        next.add(id);
      } else {
        next.delete(id);
      }
      return next;
    });
  };

  // 批量删除
  const handleBatchDelete = async () => {
    if (selectedIds.size === 0) return;
    setIsBatchDeleting(true);
    try {
      const ids = Array.from(selectedIds);
      console.log("[批量删除] 发送请求, ids:", ids);
      const res = await fetch("/api/articles/batch-delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids }),
      });
      const data = await res.json();
      console.log("[批量删除] 响应:", res.status, data);
      if (res.ok) {
        toast.success(`成功删除 ${data.deleted} 篇文章`);
        setSelectedIds(new Set());
        setBatchDeleteDialogOpen(false);
        loadArticles(page);
        loadStats();
      } else {
        toast.error(data.error || "批量删除失败");
      }
    } catch (err) {
      console.error("[批量删除] 异常:", err);
      toast.error("批量删除失败，请检查后端服务");
    } finally {
      setIsBatchDeleting(false);
    }
  };

  // 分类配置
  const categories = [
    { id: "government", name: "党政类", color: "#EF4444" },
    { id: "business", name: "商务类", color: "#3B82F6" },
    { id: "academic", name: "学术类", color: "#10B981" },
  ];

  // 加载文章列表
  const loadArticles = async (pageNum: number = 1) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(pageNum),
        page_size: "20",
      });
      if (searchQuery.trim()) params.set("q", searchQuery);
      if (categoryFilter) params.set("category_id", categoryFilter);
      if (styleFilter) params.set("style", styleFilter);

      const res = await fetch(`/api/articles?${params.toString()}`);
      const data = await res.json();
      setArticles(data.items || []);
      setTotal(data.total || 0);
      setTotalPages(data.pages || 1);
      setPage(data.page || 1);
    } catch (err) {
      toast.error("加载文章列表失败");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // 加载统计信息
  const loadStats = async () => {
    try {
      const res = await fetch("/api/articles/stats");
      const data = await res.json();
      setStats(data);
    } catch (err) {
      console.error("加载统计失败:", err);
    }
  };

  // 加载可用文体列表
  const loadStyles = async () => {
    try {
      const res = await fetch("/api/articles/styles/");
      const data = await res.json();
      setAvailableStyles(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("加载文体列表失败:", err);
    }
  };

  // 搜索文章（带筛选条件）
  const handleSearch = async () => {
    if (!searchQuery.trim() && !categoryFilter && !styleFilter) {
      loadArticles(1);
      return;
    }

    setIsSearching(true);
    try {
      const params = new URLSearchParams({
        q: searchQuery,
        page_size: "50",
      });
      if (categoryFilter) params.set("category_id", categoryFilter);
      if (styleFilter) params.set("style", styleFilter);

      const res = await fetch(`/api/articles/search?${params.toString()}`);
      const data = await res.json();
      setArticles(data.items || []);
      setTotal(data.total || 0);
      setTotalPages(1);
      setPage(1);
    } catch (err) {
      toast.error("搜索失败");
      console.error(err);
    } finally {
      setIsSearching(false);
    }
  };

  // 应用筛选 - 使用列表 API 的模糊搜索
  const applyFilters = () => {
    loadArticles(1);
  };

  // 清除筛选
  const clearFilters = () => {
    setCategoryFilter("");
    setStyleFilter("");
    setSearchQuery("");
    loadArticles(1);
  };

  // 是否有筛选条件
  const hasFilters = categoryFilter || styleFilter || searchQuery.trim();

  // 删除文章
  const handleDelete = async (article: Article) => {
    if (!confirm(`确定删除文章 "${article.title}" 吗？`)) return;

    try {
      await fetch(`/api/articles/${article.id}`, { method: "DELETE" });
      toast.success("文章已删除");
      loadArticles(page);
      loadStats();
    } catch (err) {
      toast.error("删除失败");
      console.error(err);
    }
  };

  // 下载文章为 MD 文件
  const handleDownload = async (article: Article) => {
    try {
      // 下载时获取完整内容
      const res = await fetch(`/api/articles/${article.id}`);
      const fullArticle = await res.json();

      // 构建 MD 文件内容
      let mdContent = `---\n`;
      mdContent += `title: "${fullArticle.title || '无标题'}"\n`;
      mdContent += `source: "${fullArticle.source_name || fullArticle.source_id || ''}"\n`;
      mdContent += `url: "${fullArticle.url}"\n`;
      if (fullArticle.author) mdContent += `author: "${fullArticle.author}"\n`;
      if (fullArticle.published_at) mdContent += `published_at: "${fullArticle.published_at}"\n`;
      if (fullArticle.category_name) mdContent += `category: "${fullArticle.category_name}"\n`;
      if (fullArticle.style) mdContent += `style: "${fullArticle.style}"\n`;
      if (fullArticle.keywords && fullArticle.keywords.length > 0) {
        mdContent += `keywords: [${fullArticle.keywords.map((k: string) => `"${k}"`).join(', ')}]\n`;
      }
      mdContent += `scraped_at: "${fullArticle.scraped_at}"\n`;
      mdContent += `---\n\n`;
      mdContent += `# ${fullArticle.title || '无标题'}\n\n`;
      if (fullArticle.summary) {
        mdContent += `> ${fullArticle.summary}\n\n`;
      }
      mdContent += fullArticle.content || "";

      // 生成文件名
      const fileName = `${(fullArticle.title || '无标题').replace(/[\\/:*?"<>|]/g, '_').slice(0, 50)}.md`;

      // 创建 Blob 并下载
      const blob = new Blob([mdContent], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      toast.success("下载成功");
    } catch (err) {
      toast.error("下载失败");
      console.error(err);
    }
  };

  // 检查数据库连接
  const checkDbConnection = async () => {
    setCheckingDb(true);
    try {
      const res = await fetch("/api/health/db");
      const data = await res.json();
      setDbConnected(data.database?.connected || false);
    } catch {
      setDbConnected(false);
    } finally {
      setCheckingDb(false);
    }
  };

  // 初始化
  useEffect(() => {
    loadArticles();
    loadStats();
    loadStyles();
    checkDbConnection();
  }, []);

  // 获取分类信息
  const getCategoryInfo = (id?: string) => {
    return categories.find(c => c.id === id) || null;
  };

  // 获取分类颜色
  const getCategoryBadge = (categoryId?: string, categoryName?: string) => {
    // 如果有来自后端的分类名称，直接使用
    if (categoryName) {
      const cat = getCategoryInfo(categoryId);
      const color = cat?.color || "#6B7280";
      return (
        <Badge
          variant="outline"
          style={{ borderColor: color, color: color }}
        >
          {categoryName}
        </Badge>
      );
    }
    const cat = getCategoryInfo(categoryId);
    if (!cat) return null;
    return (
      <Badge
        variant="outline"
        style={{ borderColor: cat.color, color: cat.color }}
      >
        {cat.name}
      </Badge>
    );
  };

  // 获取状态颜色
  const getStatusBadge = (status: Article["status"]) => {
    switch (status) {
      case "success":
        return <Badge variant="default">成功</Badge>;
      case "pending":
        return <Badge variant="secondary">处理中</Badge>;
      case "error":
        return <Badge variant="destructive">失败</Badge>;
      default:
        return <Badge>{status}</Badge>;
    }
  };

  // 获取文体标签颜色
  const getStyleColor = (style?: string) => {
    if (!style) return "secondary";
    if (style.includes("新闻")) return "default";
    if (style.includes("通知")) return "destructive";
    if (style.includes("会议")) return "outline";
    if (style.includes("讲话") || style.includes("发言")) return "secondary";
    return "secondary";
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">文档管理</h1>
          <p className="text-muted-foreground">管理已爬取并存入数据库的文档</p>
        </div>
        <div className="flex items-center gap-4">
          <Button
            variant="outline"
            size="sm"
            onClick={checkDbConnection}
            disabled={checkingDb}
          >
            <Database className="w-4 h-4 mr-2" />
            {checkingDb ? "检查中..." : dbConnected ? "数据库已连接" : "数据库未连接"}
          </Button>
          <Button variant="outline" size="sm" onClick={() => loadArticles(page)}>
            <RefreshCw className="w-4 h-4 mr-2" />
            刷新
          </Button>
        </div>
      </div>

      {/* 统计卡片 */}
      {stats && (
        <div className="grid grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>总文章数</CardDescription>
              <CardTitle className="text-4xl">{formatNumber(stats.total)}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>成功</CardDescription>
              <CardTitle className="text-4xl text-green-500">{formatNumber(stats.success)}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>处理中</CardDescription>
              <CardTitle className="text-4xl text-yellow-500">{formatNumber(stats.pending)}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>失败</CardDescription>
              <CardTitle className="text-4xl text-red-500">{formatNumber(stats.error)}</CardTitle>
            </CardHeader>
          </Card>
        </div>
      )}

      {/* 搜索和筛选栏 */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap gap-2 items-center">
            {/* 搜索框 */}
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="搜索文章标题、内容、摘要..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && applyFilters()}
                className="pl-10"
              />
            </div>

            {/* 分类筛选 */}
            <DropdownMenu>
              <DropdownMenuTrigger className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium border border-input bg-background hover:bg-accent hover:text-accent-foreground h-9 px-3 min-w-[100px]">
                <Filter className="w-4 h-4" />
                分类 {categoryFilter && (
                  <Badge variant="secondary" className="text-xs px-1 py-0">
                    {categories.find(c => c.id === categoryFilter)?.name || categoryFilter}
                  </Badge>
                )}
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuCheckboxItem
                  checked={!categoryFilter}
                  onCheckedChange={() => { setCategoryFilter(""); }}
                >
                  全部
                </DropdownMenuCheckboxItem>
                {categories.map(cat => (
                  <DropdownMenuCheckboxItem
                    key={cat.id}
                    checked={categoryFilter === cat.id}
                    onCheckedChange={(checked) => {
                      setCategoryFilter(checked ? cat.id : "");
                    }}
                  >
                    <span style={{ color: cat.color }}>{cat.name}</span>
                  </DropdownMenuCheckboxItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>

            {/* 文体筛选 */}
            <DropdownMenu>
              <DropdownMenuTrigger className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium border border-input bg-background hover:bg-accent hover:text-accent-foreground h-9 px-3 min-w-[100px]">
                <FileText className="w-4 h-4" />
                文体 {styleFilter && (
                  <Badge variant="secondary" className="text-xs px-1 py-0">
                    {styleFilter}
                  </Badge>
                )}
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="max-h-[300px] overflow-y-auto">
                <DropdownMenuCheckboxItem
                  checked={!styleFilter}
                  onCheckedChange={() => { setStyleFilter(""); }}
                >
                  全部
                </DropdownMenuCheckboxItem>
                {availableStyles.map(s => (
                  <DropdownMenuCheckboxItem
                    key={s.name}
                    checked={styleFilter === s.name}
                    onCheckedChange={(checked) => {
                      setStyleFilter(checked ? s.name : "");
                    }}
                  >
                    {s.name} ({s.count})
                  </DropdownMenuCheckboxItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>

            {/* 搜索按钮 */}
            <Button onClick={applyFilters} disabled={isSearching}>
              {isSearching && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              筛选
            </Button>

            {/* 清除筛选 */}
            {hasFilters && (
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                <X className="w-4 h-4 mr-1" />
                清除
              </Button>
            )}
          </div>

          {/* 筛选标签显示 */}
          {hasFilters && (
            <div className="flex gap-2 mt-3 flex-wrap">
              {categoryFilter && (
                <Badge variant="secondary" className="gap-1">
                  分类: {categories.find(c => c.id === categoryFilter)?.name}
                  <X className="w-3 h-3 cursor-pointer" onClick={() => setCategoryFilter("")} />
                </Badge>
              )}
              {styleFilter && (
                <Badge variant="secondary" className="gap-1">
                  文体: {styleFilter}
                  <X className="w-3 h-3 cursor-pointer" onClick={() => setStyleFilter("")} />
                </Badge>
              )}
              {searchQuery && (
                <Badge variant="secondary" className="gap-1">
                  关键词: {searchQuery}
                  <X className="w-3 h-3 cursor-pointer" onClick={() => setSearchQuery("")} />
                </Badge>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 文章列表 */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>文章列表</CardTitle>
              <CardDescription>
                共 {total} 篇文章
                {isSearching && searchQuery && ` (搜索结果: "${searchQuery}")`}
              </CardDescription>
            </div>
            {/* 批量操作栏 */}
            {selectedIds.size > 0 && (
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="text-sm px-3 py-1">
                  已选 {selectedIds.size} 篇
                </Badge>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => setBatchDeleteDialogOpen(true)}
                  className="gap-1"
                >
                  <Trash2 className="h-4 w-4" />
                  批量删除
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedIds(new Set())}
                >
                  <X className="h-4 w-4 mr-1" />
                  取消选择
                </Button>
              </div>
            )}
          </div>
          </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center h-40">
              <Loader2 className="w-8 h-8 animate-spin" />
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10">
                      <Checkbox
                        checked={allSelected}
                        indeterminate={someSelected}
                        onCheckedChange={(checked) => handleSelectAll(!!checked)}
                        aria-label="全选"
                      />
                    </TableHead>
                    <TableHead className="w-[250px]">标题</TableHead>
                    <TableHead>来源</TableHead>
                    <TableHead className="w-[200px]">发布链接</TableHead>
                    <TableHead>分类</TableHead>
                    <TableHead>文体</TableHead>
                    <TableHead className="w-[120px]">发布时间</TableHead>
                    <TableHead className="w-[200px]">原文信息</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {articles.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={9} className="text-center text-muted-foreground">
                        暂无文章
                      </TableCell>
                    </TableRow>
                  ) : (
                    articles.map((article) => {
                      const isSelected = selectedIds.has(article.id);
                      return (
                      <TableRow key={article.id} className={isSelected ? "bg-primary/5" : undefined}>
                        <TableCell>
                          <Checkbox
                            checked={isSelected}
                            onCheckedChange={(checked) => handleSelectOne(article.id, !!checked)}
                            aria-label={`选择 ${article.title || "无标题"}`}
                          />
                        </TableCell>
                        <TableCell className="font-medium">
                          <div className="line-clamp-2">
                            {article.title || "无标题"}
                          </div>
                        </TableCell>
                        <TableCell className="text-sm">
                          {article.sourceName ? (
                            <span className="font-medium">{article.sourceName}</span>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell className="text-sm">
                          <a
                            href={article.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-500 hover:underline truncate block max-w-[200px]"
                            title={article.url}
                          >
                            {article.url}
                          </a>
                        </TableCell>
                        <TableCell>
                          {getCategoryBadge(article.categoryId, article.categoryName)}
                        </TableCell>
                        <TableCell>
                          {article.style ? (
                            <Badge variant={getStyleColor(article.style)}>{article.style}</Badge>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {article.publishedAt ? (
                            <span className="text-sm">
                              {new Date(article.publishedAt).toLocaleDateString("zh-CN")}
                            </span>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground" title={article.summary || ""}>
                          <div className="truncate max-w-[180px]">
                            {article.summary || article.content?.slice(0, 50) + "..." || "-"}
                          </div>
                        </TableCell>
                        <TableCell className="text-right">
                          <DropdownMenu>
                            <DropdownMenuTrigger className="inline-flex items-center justify-center rounded-md text-sm font-medium hover:bg-accent hover:text-accent-foreground h-9 w-9 p-0">
                                ...
                              </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onClick={() => setSelectedArticle(article)}>
                                <Eye className="w-4 h-4 mr-2" />
                                查看详情
                              </DropdownMenuItem>
                              <DropdownMenuItem onClick={() => handleDownload(article)}>
                                <Download className="w-4 h-4 mr-2" />
                                下载 MD
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={() => handleDelete(article)}
                                className="text-red-600"
                              >
                                <Trash2 className="w-4 h-4 mr-2" />
                                删除
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    );
                    })
                  )}
                </TableBody>
              </Table>

              {/* 分页 */}
              {!isSearching && totalPages > 1 && (
                <div className="flex items-center justify-between mt-4">
                  <p className="text-sm text-muted-foreground">
                    第 {page} 页，共 {totalPages} 页
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => loadArticles(page - 1)}
                      disabled={page <= 1}
                    >
                      <ChevronLeft className="w-4 h-4 mr-1" />
                      上一页
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => loadArticles(page + 1)}
                      disabled={page >= totalPages}
                    >
                      下一页
                      <ChevronRight className="w-4 h-4 ml-1" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* 文章详情对话框 */}
      <Dialog open={!!selectedArticle} onOpenChange={() => setSelectedArticle(null)}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{selectedArticle?.title || "文章详情"}</DialogTitle>
            <DialogDescription>
              <a
                href={selectedArticle?.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-500 hover:underline"
              >
                {selectedArticle?.url}
              </a>
            </DialogDescription>
          </DialogHeader>

          {selectedArticle && (
            <Tabs defaultValue="content">
              <TabsList>
                <TabsTrigger value="content">内容</TabsTrigger>
                <TabsTrigger value="meta">元信息</TabsTrigger>
                <TabsTrigger value="keywords">关键词</TabsTrigger>
              </TabsList>

              <TabsContent value="content" className="mt-4">
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  {selectedArticle.summary && (
                    <div className="bg-muted p-4 rounded-lg mb-4">
                      <h4 className="font-semibold mb-2">摘要</h4>
                      <p className="text-sm">{selectedArticle.summary}</p>
                    </div>
                  )}
                  <div className="whitespace-pre-wrap text-sm">
                    {selectedArticle.content}
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="meta" className="mt-4">
                <dl className="grid grid-cols-2 gap-4">
                  <div>
                    <dt className="text-sm text-muted-foreground">作者</dt>
                    <dd className="font-medium">{selectedArticle.author || "-"}</dd>
                  </div>
                  <div>
                    <dt className="text-sm text-muted-foreground">发布于</dt>
                    <dd className="font-medium">{selectedArticle.publishedAt || "-"}</dd>
                  </div>
                  <div>
                    <dt className="text-sm text-muted-foreground">字数</dt>
                    <dd className="font-medium">{formatNumber(selectedArticle.wordCount)}</dd>
                  </div>
                  <div>
                    <dt className="text-sm text-muted-foreground">爬取时间</dt>
                    <dd className="font-medium">{formatDate(selectedArticle.scrapedAt)}</dd>
                  </div>
                  <div>
                    <dt className="text-sm text-muted-foreground">状态</dt>
                    <dd className="font-medium">{getStatusBadge(selectedArticle.status)}</dd>
                  </div>
                  <div>
                    <dt className="text-sm text-muted-foreground">来源分类</dt>
                    <dd className="font-medium">{getCategoryBadge(selectedArticle.categoryId, selectedArticle.categoryName) || selectedArticle.categoryName || selectedArticle.categoryId || "-"}</dd>
                  </div>
                  <div>
                    <dt className="text-sm text-muted-foreground">文体</dt>
                    <dd className="font-medium">
                      {selectedArticle.style ? (
                        <Badge variant={getStyleColor(selectedArticle.style)}>
                          {selectedArticle.style}
                        </Badge>
                      ) : "-"}
                    </dd>
                  </div>
                </dl>
              </TabsContent>

              <TabsContent value="keywords" className="mt-4">
                {selectedArticle.keywords && selectedArticle.keywords.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {selectedArticle.keywords.map((kw, i) => (
                      <Badge key={i} variant="secondary">
                        {kw}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-muted-foreground">暂无关键词</p>
                )}
              </TabsContent>
            </Tabs>
          )}
        </DialogContent>
      </Dialog>

      {/* 批量删除确认对话框 */}
      <Dialog open={batchDeleteDialogOpen} onOpenChange={setBatchDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              确认批量删除
            </DialogTitle>
            <DialogDescription>
              此操作将永久删除以下 {selectedIds.size} 篇文章，且不可恢复。
            </DialogDescription>
          </DialogHeader>

          <div className="max-h-[200px] overflow-y-auto border rounded-lg p-2 text-sm space-y-1">
            {articles
              .filter(a => selectedIds.has(a.id))
              .map(a => (
                <div key={a.id} className="truncate py-0.5 px-2 rounded hover:bg-muted">
                  {a.title || "无标题"}
                </div>
              ))}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setBatchDeleteDialogOpen(false)}
              disabled={isBatchDeleting}
            >
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={(e: React.MouseEvent) => {
                e.preventDefault();
                console.log("[批量删除] 按钮被点击, selectedIds:", Array.from(selectedIds));
                setBatchDeleteDialogOpen(false);
                handleBatchDelete();
              }}
              disabled={isBatchDeleting}
              className="gap-1"
            >
              {isBatchDeleting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  删除中...
                </>
              ) : (
                <>
                  <Trash2 className="h-4 w-4" />
                  确认删除 {selectedIds.size} 篇
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}