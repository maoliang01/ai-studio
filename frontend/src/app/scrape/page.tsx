"use client";

import { useState, useEffect } from "react";
import { useScrapeStore } from "@/stores/scrape-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  Globe,
  Search,
  Link2,
  Copy,
  Download,
  ChevronDown,
  ChevronUp,
  Clock,
  CheckCircle2,
  AlertCircle,
  Loader2,
  FileText,
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
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ScrapeResult } from "@/types";

export default function ScrapePage() {
  const [url, setUrl] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [expandedCard, setExpandedCard] = useState<string | null>(null);
  const [maxArticles, setMaxArticles] = useState(10);
  const [advancedOptions, setAdvancedOptions] = useState({
    extractContent: true,
    fetchHtml: false,
    preserveFormat: false,
    maxDepth: 0,
    timeout: 30,
  });

  const {
    results,
    isScraping,
    currentResult,
    error,
    progress,
    scrapeUrl,
    deepScrape,
    clearResults,
    setCurrentResult,
  } = useScrapeStore();

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

    // 智能选择爬取方式
    if (isArticleUrl(url)) {
      // 如果是文章详情页，直接单页爬取
      console.log('检测到文章详情页，使用单页爬取');
      await scrapeUrl(url, advancedOptions);
    } else {
      // 如果是列表页，使用深度爬取
      console.log('检测到列表页，使用深度爬取');
      await deepScrape(url, maxArticles, advancedOptions);
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

  // 导出单个结果为文件
  const exportAsFile = (item: ScrapeResult) => {
    const blob = new Blob(
      [
        `# ${item.title}\n\n`,
        `URL: ${item.url}\n`,
        item.author ? `作者: ${item.author}\n` : "",
        item.publishedAt ? `发布时间: ${item.publishedAt}\n` : "",
        item.keywords?.length ? `关键字: ${item.keywords.join(", ")}\n` : "",
        `\n## 摘要\n\n${item.summary || ""}\n\n`,
        `## 正文\n\n${item.content}`,
      ],
      { type: "text/markdown" }
    );
    const filename = `${item.title.replace(/[^a-zA-Z0-9一-龥]/g, "_").substring(0, 30)}.md`;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
  };

  // 批量导出所有结果
  const exportAllResults = () => {
    results.forEach((item, index) => {
      setTimeout(() => exportAsFile(item), index * 500);
    });
  };

  // 渲染单个文章卡片
  const renderArticleCard = (item: ScrapeResult, isSelected: boolean) => (
    <Card
      key={`${item.url}-${item.scrapedAt}`}
      className={cn(
        "transition-all cursor-pointer hover:shadow-md",
        isSelected && "ring-2 ring-primary"
      )}
      onClick={() => setCurrentResult(item)}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
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
        {/* 文章元信息 */}
        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
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
                摘要 MD
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

        {/* 展开的 MD 文档内容 */}
        {expandedCard === item.url && (
          <div className="mt-2 p-3 bg-muted/50 rounded-lg">
            <div className="text-xs max-h-96 overflow-y-auto prose prose-sm dark:prose-invert max-w-none">
              {/* MD 文档头部：标题 */}
              <h1 className="text-lg font-bold mb-2">{item.title || "无标题"}</h1>

              {/* 元信息 */}
              <div className="flex flex-wrap gap-3 text-xs text-muted-foreground mb-3 pb-2 border-b">
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

              {/* 摘要 */}
              {item.summary && (
                <>
                  <h2 className="text-sm font-semibold mb-1">摘要</h2>
                  <p className="text-sm text-muted-foreground mb-3">{item.summary}</p>
                </>
              )}

              {/* 关键字 */}
              {item.keywords && item.keywords.length > 0 && (
                <>
                  <h2 className="text-sm font-semibold mb-1">关键字</h2>
                  <div className="flex flex-wrap gap-1 mb-3">
                    {item.keywords.map((keyword, index) => (
                      <Badge key={index} variant="outline" className="text-xs">
                        <Tag className="h-2 w-2 mr-1" />
                        {keyword}
                      </Badge>
                    ))}
                  </div>
                </>
              )}

              {/* 正文 */}
              <h2 className="text-sm font-semibold mb-1">正文</h2>
              <div className="whitespace-pre-wrap text-sm leading-relaxed">
                {item.content || "未获取到内容"}
              </div>
            </div>
          </div>
        )}

        {/* 错误信息 */}
        {item.status === "error" && item.errorMessage && (
          <div className="p-2 bg-destructive/10 text-destructive rounded text-sm">
            {item.errorMessage}
          </div>
        )}
      </CardContent>
    </Card>
  );

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
                      onChange={(e) => setUrl(e.target.value)}
                      placeholder="输入列表页 URL，例如：https://news.ycombinator.com"
                      className="pl-9"
                      onKeyDown={(e) => e.key === "Enter" && !isScraping && handleDeepScrape()}
                    />
                  </div>
                  <Button
                    onClick={handleDeepScrape}
                    disabled={!url.trim() || isScraping}
                    className="gap-2"
                  >
                    {isScraping ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        爬取中...
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4" />
                        智能爬取
                      </>
                    )}
                  </Button>
                </div>

                {/* 深度爬取选项 */}
                <div className="flex items-center gap-4 p-3 bg-primary/10 rounded-lg">
                  <div className="flex items-center gap-2">
                    <Layers className="h-4 w-4 text-primary" />
                    <span className="text-sm">自动识别文章链接并爬取</span>
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
                  <p className="text-muted-foreground">正在智能识别并爬取文章...</p>
                  <p className="text-xs text-muted-foreground mt-2">
                    1. 解析列表页 → 2. 识别文章链接 → 3. 爬取正文内容 → 4. 提取元信息
                  </p>
                </div>
              </Card>
            )}

            {/* 文章卡片列表 */}
            {!isScraping && results.length > 0 && (
              <div className="space-y-4">
                {/* 批量操作栏 */}
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">
                    共 {results.length} 篇文章
                  </span>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" className="gap-2" onClick={exportAllResults}>
                      <Download className="h-4 w-4" />
                      全部导出
                    </Button>
                    <Button variant="outline" size="sm" className="gap-2">
                      <Download className="h-4 w-4" />
                      批量导入知识库
                    </Button>
                  </div>
                </div>

                {/* 文章卡片 */}
                {results.map((item) => renderArticleCard(item, currentResult === item))}
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
    </div>
  );
}