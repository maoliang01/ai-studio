"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
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
  BookOpen,
  ChevronDown,
  ChevronUp,
  Clock,
  CheckCircle2,
  AlertCircle,
  Loader2,
  FileText,
  History,
} from "lucide-react";

interface ScrapedResult {
  id: string;
  url: string;
  title: string;
  content: string;
  wordCount: number;
  status: "pending" | "success" | "error";
  errorMessage?: string;
  scrapedAt: Date;
}

const mockHistory: ScrapedResult[] = [
  {
    id: "1",
    url: "https://example.com/article-1",
    title: "示例文章 1",
    content: "这是文章的内容摘要...",
    wordCount: 3256,
    status: "success",
    scrapedAt: new Date(Date.now() - 3600000),
  },
  {
    id: "2",
    url: "https://example.com/article-2",
    title: "示例文章 2",
    content: "这是另一篇文章...",
    wordCount: 2156,
    status: "success",
    scrapedAt: new Date(Date.now() - 7200000),
  },
];

export default function ScrapePage() {
  const [url, setUrl] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<ScrapedResult | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [advancedOptions, setAdvancedOptions] = useState({
    extractContent: true,
    rawHtml: false,
    keepFormat: false,
    maxDepth: 3,
    timeout: 30,
  });

  const handleScrape = async () => {
    if (!url.trim()) return;

    setIsLoading(true);
    setResult(null);

    // 模拟爬取
    setTimeout(() => {
      setResult({
        id: Date.now().toString(),
        url: url,
        title: "抓取结果 - " + new URL(url).hostname,
        content: `这是一个示例抓取结果。

文章正文内容：

## 标题

这是网页的主要内容。它可能包含多paragraph。

### 子标题

更多的内容段落。

\`\`\`
代码块示例
\`\`\`

1. 列表项 1
2. 列表项 2
3. 列表项 3

[这是一个链接](https://example.com)

更多内容...`,
        wordCount: 3256,
        status: "success",
        scrapedAt: new Date(),
      });
      setIsLoading(false);
    }, 2000);
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

  return (
    <div className="flex h-full">
      {/* 主内容区 */}
      <div className="flex-1 flex flex-col">
        <div className="p-6 border-b border-border">
          <div className="max-w-3xl mx-auto">
            <h1 className="text-2xl font-semibold mb-4">网页爬取</h1>
            <p className="text-muted-foreground mb-6">
              输入网页 URL，自动提取正文内容并导入知识库
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
                      placeholder="输入网址，例如：https://example.com/article"
                      className="pl-9"
                      onKeyDown={(e) => e.key === "Enter" && handleScrape()}
                    />
                  </div>
                  <Button
                    onClick={handleScrape}
                    disabled={!url.trim() || isLoading}
                    className="gap-2"
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        抓取中...
                      </>
                    ) : (
                      <>
                        <Search className="h-4 w-4" />
                        抓取
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
                            id="raw-html"
                            checked={advancedOptions.rawHtml}
                            onCheckedChange={(checked) =>
                              setAdvancedOptions({
                                ...advancedOptions,
                                rawHtml: checked as boolean,
                              })
                            }
                          />
                          <Label htmlFor="raw-html" className="text-sm cursor-pointer">
                            仅获取 HTML
                          </Label>
                        </div>
                        <div className="flex items-center space-x-2">
                          <Checkbox
                            id="keep-format"
                            checked={advancedOptions.keepFormat}
                            onCheckedChange={(checked) =>
                              setAdvancedOptions({
                                ...advancedOptions,
                                keepFormat: checked as boolean,
                              })
                            }
                          />
                          <Label htmlFor="keep-format" className="text-sm cursor-pointer">
                            保留原始格式
                          </Label>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label className="text-sm">最大深度</Label>
                          <select
                            value={advancedOptions.maxDepth}
                            onChange={(e) =>
                              setAdvancedOptions({
                                ...advancedOptions,
                                maxDepth: parseInt(e.target.value),
                              })
                            }
                            className="w-full h-9 px-3 rounded-md border border-input bg-background text-sm"
                          >
                            <option value={1}>1</option>
                            <option value={2}>2</option>
                            <option value={3}>3</option>
                            <option value={5}>5</option>
                          </select>
                        </div>
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
          </div>
        </div>

        {/* 抓取结果 */}
        <ScrollArea className="flex-1">
          <div className="p-6 max-w-3xl mx-auto">
            {isLoading && (
              <Card className="p-8">
                <div className="flex flex-col items-center text-center">
                  <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
                  <p className="text-muted-foreground">正在抓取网页内容...</p>
                  <p className="text-xs text-muted-foreground mt-2">
                    预计需要几秒钟
                  </p>
                </div>
              </Card>
            )}

            {result && !isLoading && (
              <div className="space-y-6">
                <Card className="p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        {getStatusIcon(result.status)}
                        <h2 className="text-lg font-semibold">{result.title}</h2>
                      </div>
                      <a
                        href={result.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-primary hover:underline flex items-center gap-1"
                      >
                        <Link2 className="h-3.5 w-3.5" />
                        {result.url}
                      </a>
                    </div>
                    <Badge variant="secondary">
                      {result.wordCount.toLocaleString()} 字
                    </Badge>
                  </div>

                  <Separator className="my-4" />

                  <div className="prose prose-sm dark:prose-invert max-w-none">
                    <pre className="whitespace-pre-wrap bg-muted/50 p-4 rounded-lg text-sm max-h-96 overflow-y-auto">
                      {result.content}
                    </pre>
                  </div>

                  <Separator className="my-4" />

                  <div className="flex items-center gap-2">
                    <Button className="gap-2">
                      <Download className="h-4 w-4" />
                      导入到知识库
                    </Button>
                    <Button variant="outline" className="gap-2">
                      <Copy className="h-4 w-4" />
                      复制文本
                    </Button>
                    <Button variant="outline" className="gap-2">
                      <FileText className="h-4 w-4" />
                      查看全文
                    </Button>
                  </div>
                </Card>
              </div>
            )}

            {!result && !isLoading && (
              <Card className="p-8 text-center">
                <div className="w-16 h-16 rounded-full bg-muted mx-auto flex items-center justify-center mb-4">
                  <Globe className="h-8 w-8 text-muted-foreground" />
                </div>
                <h3 className="text-lg font-medium mb-2">输入网址开始抓取</h3>
                <p className="text-muted-foreground text-sm">
                  支持抓取新闻、文档、博客等网页内容
                </p>
              </Card>
            )}
          </div>
        </ScrollArea>
      </div>

      {/* 右侧历史记录 */}
      <div className="w-80 border-l border-border flex flex-col bg-card/50">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h3 className="font-semibold flex items-center gap-2">
            <History className="h-4 w-4" />
            历史记录
          </h3>
        </div>

        <ScrollArea className="flex-1">
          <div className="p-2 space-y-1">
            {mockHistory.map((item) => (
              <button
                key={item.id}
                onClick={() => {
                  setUrl(item.url);
                  setResult(item);
                }}
                className="w-full text-left p-3 rounded-lg hover:bg-accent transition-colors"
              >
                <div className="flex items-start gap-2">
                  {getStatusIcon(item.status)}
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm truncate">{item.title}</p>
                    <p className="text-xs text-muted-foreground truncate mt-1">
                      {item.url}
                    </p>
                    <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {new Date(item.scrapedAt).toLocaleString("zh-CN", {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                      <span>·</span>
                      <span>{item.wordCount.toLocaleString()} 字</span>
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}