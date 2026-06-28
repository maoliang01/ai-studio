"use client";

import { useState } from "react";
import { useKnowledgeStore } from "@/stores/knowledge-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  FileText,
  Search,
  Upload,
  Trash2,
  RefreshCw,
  Globe,
  Clock,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Database,
  FileUp,
  ExternalLink,
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function KnowledgePage() {
  const {
    documents,
    selectedDocumentId,
    selectDocument,
    deleteDocument,
    searchQuery,
    setSearchQuery,
    isUploading,
    setUploading,
  } = useKnowledgeStore();

  const [dragActive, setDragActive] = useState(false);
  const [searchTestQuery, setSearchTestQuery] = useState("");
  const [testResults, setTestResults] = useState<Array<{ content: string; score: number }>>([]);

  const selectedDoc = documents.find((d) => d.id === selectedDocumentId);

  const filteredDocs = documents.filter((doc) =>
    doc.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    // 模拟上传
    setUploading(true);
    setTimeout(() => setUploading(false), 2000);
  };

  const handleSearchTest = () => {
    if (!searchTestQuery.trim()) return;
    // 模拟搜索结果
    setTestResults([
      { content: "产品安装步骤首先需要...这是相关段落内容", score: 0.92 },
      { content: "系统要求：推荐使用 Chrome 浏览器...", score: 0.87 },
      { content: "常见问题解答页面包含...", score: 0.76 },
    ]);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "indexed":
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case "indexing":
        return <Loader2 className="h-4 w-4 text-yellow-500 animate-spin" />;
      case "error":
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case "indexed":
        return "已索引";
      case "indexing":
        return "索引中...";
      case "error":
        return "索引失败";
      default:
        return "等待中";
    }
  };

  return (
    <div className="flex h-full">
      {/* 左侧文档列表 */}
      <div className="w-80 border-r border-border flex flex-col bg-card/50">
        <div className="p-3 space-y-3 border-b border-border">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜索文档..."
              className="pl-9"
            />
          </div>
          <Button className="w-full gap-2">
            <Upload className="h-4 w-4" />
            上传文档
          </Button>
        </div>

        {/* 标签筛选 */}
        <div className="px-3 py-2 flex gap-2 flex-wrap border-b border-border">
          {["全部", "技术", "产品", "公司"].map((tag) => (
            <Badge
              key={tag}
              variant={tag === "全部" ? "default" : "secondary"}
              className="cursor-pointer"
            >
              {tag}
            </Badge>
          ))}
        </div>

        <ScrollArea className="flex-1">
          <div className="p-2 space-y-1">
            {filteredDocs.map((doc) => (
              <button
                key={doc.id}
                onClick={() => selectDocument(doc.id)}
                className={cn(
                  "w-full text-left p-3 rounded-lg transition-colors",
                  selectedDocumentId === doc.id
                    ? "bg-primary/10 border border-primary/20"
                    : "hover:bg-accent"
                )}
              >
                <div className="flex items-start gap-2">
                  <FileText className="h-4 w-4 shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm truncate">{doc.title}</p>
                    <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                      <span>{doc.chunkCount} 个块</span>
                      <span>·</span>
                      <div className="flex items-center gap-1">
                        {getStatusIcon(doc.status)}
                        <span>{getStatusText(doc.status)}</span>
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      {(doc.fileSize / 1024 / 1024).toFixed(1)} MB
                    </p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </ScrollArea>
      </div>

      {/* 右侧详情区域 */}
      <div className="flex-1 flex flex-col">
        {!selectedDoc ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-8">
            <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-4">
              <Database className="h-8 w-8 text-primary" />
            </div>
            <h2 className="text-xl font-semibold mb-2">知识库管理</h2>
            <p className="text-muted-foreground max-w-md">
              上传文档构建知识库，让 AI 能够基于你的资料进行回答。支持的格式包括 PDF、TXT、Markdown 等。
            </p>
          </div>
        ) : (
          <>
            <div className="p-4 border-b border-border flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold">{selectedDoc.title}</h2>
                <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Globe className="h-3.5 w-3.5" />
                    {selectedDoc.sourceType === "upload" ? "本地上传" : "网页"}
                  </span>
                  <span>{selectedDoc.chunkCount} 个块</span>
                  <span>·</span>
                  <span className="flex items-center gap-1">
                    {getStatusIcon(selectedDoc.status)}
                    {getStatusText(selectedDoc.status)}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" className="gap-1">
                  <RefreshCw className="h-3.5 w-3.5" />
                  重新索引
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-1 text-destructive hover:text-destructive"
                  onClick={() => deleteDocument(selectedDoc.id)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  删除
                </Button>
              </div>
            </div>

            <Tabs defaultValue="preview" className="flex-1 flex flex-col">
              <div className="px-4 pt-2 border-b border-border">
                <TabsList>
                  <TabsTrigger value="preview">文档预览</TabsTrigger>
                  <TabsTrigger value="search">检索测试</TabsTrigger>
                </TabsList>
              </div>

              <TabsContent value="preview" className="flex-1 m-0">
                <ScrollArea className="h-full p-4">
                  <div className="max-w-3xl mx-auto space-y-4">
                    {selectedDoc.sourceUrl && (
                      <a
                        href={selectedDoc.sourceUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 text-sm text-primary hover:underline"
                      >
                        <ExternalLink className="h-4 w-4" />
                        {selectedDoc.sourceUrl}
                      </a>
                    )}

                    <Card className="p-6 space-y-4">
                      <div className="flex items-center justify-between">
                        <h3 className="font-medium">文档块 (Chunks)</h3>
                        <Badge variant="secondary">{selectedDoc.chunkCount} 个</Badge>
                      </div>
                      <Separator />

                      {/* 模拟块内容 */}
                      {[
                        {
                          index: 1,
                          content: `产品简介

本产品是一款功能强大的 AI 工作台，旨在帮助用户更高效地完成各种 AI 相关任务。

核心功能：
- 多模型对话
- 知识库管理
- 提示词模板
- 网页爬取`,
                        },
                        {
                          index: 2,
                          content: `安装指南

1. 系统要求
   - 操作系统：Ubuntu 20.04+ / macOS 12+ / Windows 10+
   - 内存：至少 8GB RAM
   - 磁盘空间：至少 2GB 可用空间

2. 安装步骤
   - 下载对应平台的安装包
   - 运行安装程序
   - 按照提示完成安装`,
                        },
                        {
                          index: 3,
                          content: `常见问题

Q: 如何获取 API Key？
A: 请访问各模型提供商的官网注册账号并获取 API Key。

Q: 支持哪些文件格式？
A: 目前支持 PDF、TXT、Markdown、DOCX 等格式。`,
                        },
                      ].map((chunk) => (
                        <div key={chunk.index} className="space-y-2">
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className="text-xs">
                              Chunk {chunk.index}
                            </Badge>
                          </div>
                          <pre className="text-sm whitespace-pre-wrap bg-muted/50 p-3 rounded-lg">
                            {chunk.content}
                          </pre>
                        </div>
                      ))}
                    </Card>
                  </div>
                </ScrollArea>
              </TabsContent>

              <TabsContent value="search" className="flex-1 m-0 p-4">
                <div className="max-w-3xl mx-auto space-y-6">
                  <Card className="p-4">
                    <h3 className="font-medium mb-4">向量检索测试</h3>
                    <div className="flex gap-2">
                      <Input
                        value={searchTestQuery}
                        onChange={(e) => setSearchTestQuery(e.target.value)}
                        placeholder="输入查询内容..."
                        onKeyDown={(e) => e.key === "Enter" && handleSearchTest()}
                      />
                      <Button onClick={handleSearchTest}>搜索</Button>
                    </div>
                  </Card>

                  {testResults.length > 0 && (
                    <div className="space-y-3">
                      <h4 className="text-sm font-medium text-muted-foreground">
                        检索结果
                      </h4>
                      {testResults.map((result, index) => (
                        <Card key={index} className="p-4">
                          <div className="flex items-start justify-between gap-2">
                            <p className="text-sm flex-1">{result.content}</p>
                            <Badge variant="secondary">
                              {(result.score * 100).toFixed(0)}%
                            </Badge>
                          </div>
                        </Card>
                      ))}
                    </div>
                  )}
                </div>
              </TabsContent>
            </Tabs>
          </>
        )}
      </div>

      {/* 上传弹窗覆盖层 */}
      {dragActive && (
        <div
          className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-center justify-center"
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <Card className="w-[500px] p-8 border-2 border-dashed border-primary/50">
            <div className="flex flex-col items-center text-center">
              <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                <FileUp className="h-8 w-8 text-primary" />
              </div>
              <h3 className="text-lg font-semibold mb-2">拖拽文件上传</h3>
              <p className="text-muted-foreground">
                支持 PDF、TXT、MD、DOCX 等格式
              </p>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}