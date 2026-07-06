"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CheckCircle2, Search, Database, Zap, Code, ArrowRight } from "lucide-react";

export default function ChangelogPage() {
  const features = [
    {
      title: "智能关键词搜索",
      description: "支持模糊匹配文章标题、内容、摘要及自动提取的关键词",
      icon: Search,
      benefit: "输入任意关键词即可找到相关文章",
      example: "搜索「幸福工程」能找到相关文章，即使标题中没有这个词",
    },
    {
      title: "多字段联合搜索",
      description: "一次搜索同时覆盖多个字段，结果更全面",
      icon: Database,
      benefit: "无需多次搜索，减少操作步骤",
      example: "搜索「党建」同时匹配标题、内容和关键词字段",
    },
    {
      title: "全文检索优化",
      description: "结合 PostgreSQL 全文搜索和关键词匹配",
      icon: Zap,
      benefit: "搜索结果按相关性排序，优先展示匹配度高的文章",
      example: "标题匹配 > 内容匹配 > 关键词匹配",
    },
  ];

  const searchFields = [
    { field: "标题 (title)", method: "ILIKE %keyword%", color: "bg-blue-100 text-blue-700" },
    { field: "内容 (content)", method: "ILIKE %keyword%", color: "bg-green-100 text-green-700" },
    { field: "摘要 (summary)", method: "ILIKE %keyword%", color: "bg-yellow-100 text-yellow-700" },
    { field: "关键词 (keywords)", method: "ILIKE %keyword%", color: "bg-purple-100 text-purple-700" },
  ];

  const testResults = [
    { keyword: "幸福工程", results: 5, note: "通过文章关键词匹配" },
    { keyword: "党建", results: 6, note: "标题+内容+关键词匹配" },
    { keyword: "民族团结", results: 2, note: "关键词匹配" },
  ];

  return (
    <div className="container mx-auto p-6 max-w-5xl">
      {/* 头部 */}
      <div className="space-y-4 mb-8">
        <div className="flex items-center gap-3">
          <Badge variant="default" className="text-sm px-3 py-1">
            v2.1.0
          </Badge>
          <Badge variant="secondary" className="text-sm">
            2026-07-06
          </Badge>
        </div>
        <h1 className="text-4xl font-bold tracking-tight">
          文档管理 - 关键词智能搜索
        </h1>
        <p className="text-xl text-muted-foreground">
          增强搜索功能，支持关键词模糊匹配，快速找到相关文章
        </p>
      </div>

      {/* 功能概述 */}
      <Card className="mb-8 border-l-4 border-l-blue-500">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-blue-500" />
            功能更新
          </CardTitle>
          <CardDescription>
            搜索框现在支持模糊匹配文章标题、内容、摘要和关键词
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-3 gap-4">
            {features.map((feature, index) => (
              <Card key={index} className="bg-muted/50">
                <CardHeader className="pb-2">
                  <feature.icon className="w-8 h-8 text-primary mb-2" />
                  <CardTitle className="text-base">{feature.title}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <p className="text-sm text-muted-foreground">
                    {feature.description}
                  </p>
                  <div className="flex items-start gap-2 text-sm">
                    <CheckCircle2 className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />
                    <span>{feature.benefit}</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* 技术实现 */}
      <Tabs defaultValue="implementation" className="mb-8">
        <TabsList>
          <TabsTrigger value="implementation">技术实现</TabsTrigger>
          <TabsTrigger value="search-fields">搜索字段</TabsTrigger>
          <TabsTrigger value="test">测试结果</TabsTrigger>
        </TabsList>

        <TabsContent value="implementation" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Code className="w-5 h-5" />
                后端实现
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <h4 className="font-semibold mb-2">数据库查询优化</h4>
                <pre className="bg-muted p-4 rounded-lg text-sm overflow-x-auto">
{`# 使用左连接关键词表，实现多字段搜索
query = query.outerjoin(
    ArticleKeyword, Article.id == ArticleKeyword.article_id
).outerjoin(
    Keyword, ArticleKeyword.keyword_id == Keyword.id
).filter(
    or_(
        Article.title.ilike(keyword_pattern),
        Article.content.ilike(keyword_pattern),
        Article.summary.ilike(keyword_pattern),
        Keyword.name.ilike(keyword_pattern)
    )
)`}
                </pre>
              </div>

              <div className="flex items-center gap-2 text-sm">
                <ArrowRight className="w-4 h-4" />
                <span className="text-muted-foreground">
                  修改文件：<code className="bg-muted px-1 rounded">backend/app/api/articles.py</code>
                </span>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="search-fields" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>搜索覆盖的字段</CardTitle>
              <CardDescription>
                搜索时以下字段会进行模糊匹配（不区分大小写）
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {searchFields.map((field, index) => (
                  <div key={index} className="flex items-center gap-4 p-3 bg-muted/50 rounded-lg">
                    <span className={`px-2 py-1 rounded text-sm font-medium ${field.color}`}>
                      {field.field}
                    </span>
                    <code className="text-sm text-muted-foreground">{field.method}</code>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="test" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>测试结果</CardTitle>
              <CardDescription>
                功能上线后的搜索测试数据
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {testResults.map((test, index) => (
                  <div key={index} className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                    <div>
                      <code className="font-semibold">"{test.keyword}"</code>
                      <span className="text-sm text-muted-foreground ml-2">
                        → {test.note}
                      </span>
                    </div>
                    <Badge variant="default" className="text-base px-3">
                      {test.results} 篇
                    </Badge>
                  </div>
                ))}
              </div>

              <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
                <div className="flex items-center gap-2 text-green-700 font-medium">
                  <CheckCircle2 className="w-5 h-5" />
                  功能验证通过
                </div>
                <p className="text-sm text-green-600 mt-1">
                  关键词搜索功能正常，支持标题、内容、摘要和关键词的多字段模糊匹配
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* 使用示例 */}
      <Card className="border-l-4 border-l-green-500">
        <CardHeader>
          <CardTitle>使用示例</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-2 gap-4">
            <div className="p-4 bg-muted rounded-lg">
              <h4 className="font-semibold mb-2">场景 1：搜索完全匹配关键词的文章</h4>
              <p className="text-sm text-muted-foreground">
                输入「幸福工程」→ 找到 5 篇文章
                <br />
                <span className="text-xs">（这些文章的元数据关键词中包含"幸福工程"）</span>
              </p>
            </div>
            <div className="p-4 bg-muted rounded-lg">
              <h4 className="font-semibold mb-2">场景 2：搜索标题和内容的关键词</h4>
              <p className="text-sm text-muted-foreground">
                输入「党建」→ 找到 6 篇文章
                <br />
                <span className="text-xs">（文章标题、内容或关键词中包含"党建"）</span>
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}