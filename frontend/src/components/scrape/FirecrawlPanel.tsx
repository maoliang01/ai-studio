"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  CheckCircle2,
  AlertCircle,
  Loader2,
  Flame,
  Globe,
  Map,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Copy,
  RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  checkFirecrawlHealth,
  firecrawlScrape,
  firecrawlMap,
  type FirecrawlHealthResult,
  type FirecrawlScrapeResult,
  type FirecrawlMapResult,
} from "@/lib/api";

interface FirecrawlPanelProps {
  initialUrl?: string;
  onContentExtracted?: (content: string, metadata: {
    title?: string;
    links?: string[];
  }) => void;
  compact?: boolean;
}

export function FirecrawlPanel({
  initialUrl = "",
  onContentExtracted,
  compact = false
}: FirecrawlPanelProps) {
  const [url, setUrl] = useState(initialUrl);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [healthStatus, setHealthStatus] = useState<FirecrawlHealthResult | null>(null);
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);
  const [isScraping, setIsScraping] = useState(false);
  const [isGettingMap, setIsGettingMap] = useState(false);
  const [scrapeResult, setScrapeResult] = useState<FirecrawlScrapeResult | null>(null);
  const [mapResult, setMapResult] = useState<FirecrawlMapResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [formats, setFormats] = useState<string[]>(["markdown", "html", "links"]);

  // 检查服务状态
  const checkHealth = async () => {
    setIsCheckingHealth(true);
    setError(null);
    try {
      const result = await checkFirecrawlHealth();
      setHealthStatus(result);
    } catch (e) {
      setHealthStatus({
        available: false,
        url: "http://localhost:3002",
        message: e instanceof Error ? e.message : "检查失败"
      });
    } finally {
      setIsCheckingHealth(false);
    }
  };

  // 爬取网页
  const handleScrape = async () => {
    if (!url.trim()) return;

    setIsScraping(true);
    setError(null);
    setScrapeResult(null);
    setMapResult(null);

    try {
      const result = await firecrawlScrape(url, formats);
      setScrapeResult(result);

      if (result.success && onContentExtracted && result.content) {
        onContentExtracted(result.content, {
          title: result.title,
          links: result.links,
        });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "爬取失败");
    } finally {
      setIsScraping(false);
    }
  };

  // 获取网站地图
  const handleGetMap = async () => {
    if (!url.trim()) return;

    setIsGettingMap(true);
    setError(null);
    setScrapeResult(null);
    setMapResult(null);

    try {
      const result = await firecrawlMap(url);
      setMapResult(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "获取地图失败");
    } finally {
      setIsGettingMap(false);
    }
  };

  // 复制内容
  const handleCopyContent = () => {
    if (scrapeResult?.content) {
      navigator.clipboard.writeText(scrapeResult.content);
    }
  };

  // 复制链接列表
  const handleCopyLinks = () => {
    if (mapResult?.links) {
      navigator.clipboard.writeText(mapResult.links.join("\n"));
    } else if (scrapeResult?.links) {
      navigator.clipboard.writeText(scrapeResult.links.join("\n"));
    }
  };

  // 切换格式选项
  const toggleFormat = (format: string) => {
    setFormats(prev =>
      prev.includes(format)
        ? prev.filter(f => f !== format)
        : [...prev, format]
    );
  };

  // 页面加载时检查状态
  if (!healthStatus && !isCheckingHealth) {
    checkHealth();
  }

  return (
    <Card className={cn(compact ? "border-2 border-orange-200 dark:border-orange-800" : "")}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Flame className="h-5 w-5 text-orange-500" />
            Firecrawl 爬虫
            {healthStatus && (
              <Badge
                variant={healthStatus.available ? "default" : "destructive"}
                className={cn(
                  "text-xs ml-2",
                  healthStatus.available && "bg-green-500"
                )}
              >
                {healthStatus.available ? "在线" : "离线"}
              </Badge>
            )}
          </CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={checkHealth}
            disabled={isCheckingHealth}
          >
            <RefreshCw className={cn("h-4 w-4", isCheckingHealth && "animate-spin")} />
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* URL 输入 */}
        <div className="flex gap-2">
          <Input
            placeholder="输入网页 URL..."
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleScrape()}
          />
        </div>

        {/* 操作按钮 */}
        <div className="flex gap-2">
          <Button
            onClick={handleScrape}
            disabled={isScraping || !url.trim() || !healthStatus?.available}
            className="flex-1 gap-2"
            variant={scrapeResult?.success ? "outline" : "default"}
          >
            {isScraping ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                爬取中...
              </>
            ) : (
              <>
                <Globe className="h-4 w-4" />
                抓取网页
              </>
            )}
          </Button>
          <Button
            onClick={handleGetMap}
            disabled={isGettingMap || !url.trim() || !healthStatus?.available}
            variant="outline"
            className="gap-2"
          >
            {isGettingMap ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
              </>
            ) : (
              <>
                <Map className="h-4 w-4" />
              </>
            )}
          </Button>
        </div>

        {/* 高级选项 */}
        <div>
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            高级选项
            {showAdvanced ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </button>

          {showAdvanced && (
            <div className="mt-2 p-3 bg-muted/50 rounded-lg space-y-2">
              <Label className="text-sm">输出格式</Label>
              <div className="flex flex-wrap gap-3">
                {["markdown", "html", "links", "screenshot"].map((format) => (
                  <div key={format} className="flex items-center space-x-2">
                    <Checkbox
                      id={`format-${format}`}
                      checked={formats.includes(format)}
                      onCheckedChange={() => toggleFormat(format)}
                    />
                    <Label htmlFor={`format-${format}`} className="text-sm cursor-pointer capitalize">
                      {format}
                    </Label>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 错误提示 */}
        {error && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 text-destructive">
            <AlertCircle className="h-4 w-4" />
            <span className="text-sm">{error}</span>
          </div>
        )}

        {/* 爬取结果 */}
        {scrapeResult && (
          <div className="space-y-3 pt-2 border-t">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {scrapeResult.success ? (
                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                ) : (
                  <AlertCircle className="h-4 w-4 text-red-500" />
                )}
                <span className="text-sm font-medium">
                  {scrapeResult.success ? "抓取成功" : "抓取失败"}
                </span>
              </div>
              {scrapeResult.success && (
                <Button variant="ghost" size="sm" onClick={handleCopyContent}>
                  <Copy className="h-3.5 w-3.5 mr-1" />
                  复制内容
                </Button>
              )}
            </div>

            {scrapeResult.success && (
              <>
                {scrapeResult.title && (
                  <h4 className="font-medium text-sm">{scrapeResult.title}</h4>
                )}
                <div className="text-xs text-muted-foreground">
                  字数: {scrapeResult.word_count} | 链接: {scrapeResult.links?.length || 0}
                </div>
                {scrapeResult.content && (
                  <ScrollArea className="h-[200px] rounded-md border p-2">
                    <pre className="text-xs whitespace-pre-wrap">
                      {scrapeResult.content.slice(0, 2000)}
                      {scrapeResult.content.length > 2000 && "..."}
                    </pre>
                  </ScrollArea>
                )}
              </>
            )}

            {scrapeResult.error_message && (
              <p className="text-sm text-muted-foreground">{scrapeResult.error_message}</p>
            )}
          </div>
        )}

        {/* 地图结果 */}
        {mapResult && (
          <div className="space-y-3 pt-2 border-t">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {mapResult.success ? (
                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                ) : (
                  <AlertCircle className="h-4 w-4 text-red-500" />
                )}
                <span className="text-sm font-medium">
                  {mapResult.success ? `发现 ${mapResult.links.length} 个链接` : "获取失败"}
                </span>
              </div>
              {mapResult.success && (
                <Button variant="ghost" size="sm" onClick={handleCopyLinks}>
                  <Copy className="h-3.5 w-3.5 mr-1" />
                  复制链接
                </Button>
              )}
            </div>

            {mapResult.success && mapResult.links.length > 0 && (
              <ScrollArea className="h-[200px] rounded-md border p-2">
                <div className="space-y-1">
                  {mapResult.links.slice(0, 50).map((link, index) => (
                    <a
                      key={index}
                      href={link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-xs text-primary hover:underline truncate"
                    >
                      <ExternalLink className="h-2.5 w-2.5 shrink-0" />
                      {link}
                    </a>
                  ))}
                  {mapResult.links.length > 50 && (
                    <p className="text-xs text-muted-foreground pt-2">
                      ...还有 {mapResult.links.length - 50} 个链接
                    </p>
                  )}
                </div>
              </ScrollArea>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}