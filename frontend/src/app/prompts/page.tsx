"use client";

import { useState } from "react";
import { usePromptsStore } from "@/stores/prompts-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  FileText,
  Search,
  Plus,
  Trash2,
  Star,
  Send,
  Copy,
  Edit,
  Tag,
  MessageSquare,
  Clock,
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function PromptsPage() {
  const {
    prompts,
    categories,
    selectedCategoryId,
    selectCategory,
    selectedPromptId,
    selectPrompt,
    addPrompt,
    updatePrompt,
    deletePrompt,
    toggleFavorite,
    searchQuery,
    setSearchQuery,
  } = usePromptsStore();

  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState<{
    title: string;
    content: string;
    category: string;
  }>({ title: "", content: "", category: "" });

  const selectedPrompt = prompts.find((p) => p.id === selectedPromptId);

  const filteredPrompts = prompts.filter((prompt) => {
    const matchesCategory = !selectedCategoryId || prompt.category === selectedCategoryId;
    const matchesSearch =
      !searchQuery ||
      prompt.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      prompt.content.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  const handleCreatePrompt = () => {
    setEditingPrompt({ title: "", content: "", category: "coding" });
    setIsEditorOpen(true);
  };

  const handleEditPrompt = (prompt: typeof selectedPrompt) => {
    if (!prompt) return;
    setEditingPrompt({
      title: prompt.title,
      content: prompt.content,
      category: prompt.category,
    });
    setIsEditorOpen(true);
  };

  const handleSavePrompt = () => {
    if (!editingPrompt.title.trim() || !editingPrompt.content.trim()) return;

    const newPrompt = {
      id: Date.now().toString(),
      title: editingPrompt.title,
      content: editingPrompt.content,
      category: editingPrompt.category,
      variables: extractVariables(editingPrompt.content),
      usageCount: 0,
      isFavorite: false,
      isPublic: false,
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    addPrompt(newPrompt);
    selectPrompt(newPrompt.id);
    setIsEditorOpen(false);
  };

  const extractVariables = (content: string) => {
    const matches = content.match(/\{\{(\w+)\}\}/g) || [];
    return [...new Set(matches)].map((varName) => ({
      name: varName.replace(/\{\{|\}\}/g, ""),
      defaultValue: "",
      description: "",
    }));
  };

  return (
    <div className="flex h-full">
      {/* 左侧分类列表 */}
      <div className="w-56 border-r border-border flex flex-col bg-card/50">
        <div className="p-3 border-b border-border">
          <Button
            onClick={handleCreatePrompt}
            className="w-full justify-start gap-2"
            variant="default"
          >
            <Plus className="h-4 w-4" />
            新建提示词
          </Button>
        </div>

        <ScrollArea className="flex-1">
          <div className="p-2 space-y-1">
            <button
              onClick={() => selectCategory(null)}
              className={cn(
                "w-full text-left px-3 py-2 rounded-lg text-sm transition-colors",
                !selectedCategoryId && "bg-primary/10 text-primary"
              )}
            >
              <span className="flex items-center justify-between">
                全部
                <Badge variant="secondary" className="text-xs">
                  {prompts.length}
                </Badge>
              </span>
            </button>

            <Separator className="my-2" />

            {categories.map((category) => (
              <button
                key={category.id}
                onClick={() => selectCategory(category.id)}
                className={cn(
                  "w-full text-left px-3 py-2 rounded-lg text-sm transition-colors",
                  selectedCategoryId === category.id && "bg-primary/10 text-primary"
                )}
              >
                <span className="flex items-center justify-between">
                  {category.name}
                  <Badge variant="secondary" className="text-xs">
                    {category.count}
                  </Badge>
                </span>
              </button>
            ))}
          </div>
        </ScrollArea>
      </div>

      {/* 中间提示词列表 */}
      <div className="w-80 border-r border-border flex flex-col bg-card/50">
        <div className="p-3 border-b border-border">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜索提示词..."
              className="pl-9"
            />
          </div>
        </div>

        <ScrollArea className="flex-1">
          <div className="p-2 space-y-1">
            {filteredPrompts.map((prompt) => (
              <button
                key={prompt.id}
                onClick={() => selectPrompt(prompt.id)}
                className={cn(
                  "w-full text-left p-3 rounded-lg transition-colors group",
                  selectedPromptId === prompt.id
                    ? "bg-primary/10 border border-primary/20"
                    : "hover:bg-accent"
                )}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 shrink-0 mt-0.5" />
                    <span className="font-medium text-sm">{prompt.title}</span>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleFavorite(prompt.id);
                    }}
                    className={cn(
                      "p-1",
                      prompt.isFavorite && "text-yellow-500"
                    )}
                  >
                    <Star className={cn("h-3.5 w-3.5", prompt.isFavorite && "fill-current")} />
                  </button>
                </div>
                <p className="text-xs text-muted-foreground mt-2 line-clamp-2">
                  {prompt.content.slice(0, 80)}...
                </p>
                <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                  <Badge variant="secondary" className="text-xs">
                    {categories.find((c) => c.id === prompt.category)?.name || prompt.category}
                  </Badge>
                  <span>·</span>
                  <span>{prompt.variables.length} 个变量</span>
                  <span>·</span>
                  <span>使用 {prompt.usageCount} 次</span>
                </div>
              </button>
            ))}
          </div>
        </ScrollArea>
      </div>

      {/* 右侧详情区域 */}
      <div className="flex-1 flex flex-col">
        {!selectedPrompt ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-8">
            <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-4">
              <FileText className="h-8 w-8 text-primary" />
            </div>
            <h2 className="text-xl font-semibold mb-2">提示词管理</h2>
            <p className="text-muted-foreground max-w-md">
              创建和管理提示词模板，支持变量占位符。可以在对话中快速调用，或者分享给团队使用。
            </p>
          </div>
        ) : (
          <>
            <div className="p-4 border-b border-border flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold">{selectedPrompt.title}</h2>
                <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
                  <Badge variant="secondary">
                    {categories.find((c) => c.id === selectedPrompt.category)?.name ||
                      selectedPrompt.category}
                  </Badge>
                  <span className="flex items-center gap-1">
                    <Tag className="h-3.5 w-3.5" />
                    {selectedPrompt.variables.length} 个变量
                  </span>
                  <span className="flex items-center gap-1">
                    <MessageSquare className="h-3.5 w-3.5" />
                    使用 {selectedPrompt.usageCount} 次
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" className="gap-1">
                  <Send className="h-3.5 w-3.5" />
                  在对话中使用
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-1"
                  onClick={() => handleEditPrompt(selectedPrompt)}
                >
                  <Edit className="h-3.5 w-3.5" />
                  编辑
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-1"
                  onClick={() => {
                    navigator.clipboard.writeText(selectedPrompt.content);
                  }}
                >
                  <Copy className="h-3.5 w-3.5" />
                  复制
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-1 text-destructive hover:text-destructive"
                  onClick={() => deletePrompt(selectedPrompt.id)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  删除
                </Button>
              </div>
            </div>

            <ScrollArea className="flex-1 p-4">
              <div className="max-w-3xl mx-auto space-y-6">
                {/* 提示词内容 */}
                <Card className="p-6">
                  <h3 className="font-medium mb-4">提示词内容</h3>
                  <pre className="text-sm whitespace-pre-wrap bg-muted/50 p-4 rounded-lg font-mono">
                    {selectedPrompt.content}
                  </pre>
                </Card>

                {/* 变量定义 */}
                {selectedPrompt.variables.length > 0 && (
                  <Card className="p-6">
                    <h3 className="font-medium mb-4">变量定义</h3>
                    <div className="space-y-3">
                      {selectedPrompt.variables.map((variable) => (
                        <div
                          key={variable.name}
                          className="flex items-center gap-4 p-3 bg-muted/50 rounded-lg"
                        >
                          <code className="px-2 py-1 bg-primary/10 text-primary rounded text-sm font-mono">
                            {`{{${variable.name}}}`}
                          </code>
                          <div className="flex-1">
                            <p className="text-sm font-medium">{variable.description || "未描述"}</p>
                            {variable.defaultValue && (
                              <p className="text-xs text-muted-foreground mt-1">
                                默认值: {variable.defaultValue}
                              </p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}

                {/* 元信息 */}
                <Card className="p-6">
                  <h3 className="font-medium mb-4">元信息</h3>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="text-muted-foreground">创建时间</p>
                      <p>{new Date(selectedPrompt.createdAt).toLocaleDateString("zh-CN")}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">更新时间</p>
                      <p>{new Date(selectedPrompt.updatedAt).toLocaleDateString("zh-CN")}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">是否公开</p>
                      <p>{selectedPrompt.isPublic ? "是" : "否"}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">收藏</p>
                      <p>{selectedPrompt.isFavorite ? "是" : "否"}</p>
                    </div>
                  </div>
                </Card>
              </div>
            </ScrollArea>
          </>
        )}
      </div>

      {/* 编辑弹窗 */}
      <Dialog open={isEditorOpen} onOpenChange={setIsEditorOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {editingPrompt.title ? "编辑提示词" : "新建提示词"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">标题</label>
              <Input
                value={editingPrompt.title}
                onChange={(e) =>
                  setEditingPrompt({ ...editingPrompt, title: e.target.value })
                }
                placeholder="输入提示词标题"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">分类</label>
              <select
                value={editingPrompt.category}
                onChange={(e) =>
                  setEditingPrompt({ ...editingPrompt, category: e.target.value })
                }
                className="w-full h-10 px-3 rounded-md border border-input bg-background text-sm"
              >
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">提示词内容</label>
              <Textarea
                value={editingPrompt.content}
                onChange={(e) =>
                  setEditingPrompt({ ...editingPrompt, content: e.target.value })
                }
                placeholder="输入提示词内容，使用 {{variable}} 定义变量"
                rows={12}
                className="font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">
                使用 <code className="px-1 bg-muted rounded">{"{{变量名}}"}</code>{" "}
                定义变量，例如：{"{{language}}"}
              </p>
            </div>

            <div className="flex justify-end gap-2 pt-4">
              <Button variant="outline" onClick={() => setIsEditorOpen(false)}>
                取消
              </Button>
              <Button onClick={handleSavePrompt}>保存</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}