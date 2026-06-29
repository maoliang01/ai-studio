"use client";

import { useState, useEffect } from "react";
import { useSettingsStore } from "@/stores/settings-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Bot,
  Plus,
  Trash2,
  Edit2,
  Zap,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Link2,
  Brain,
  Image,
  Clock,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ModelType } from "@/types";

// 模型配置类型（与 settings-store 保持一致）
interface ModelConfig {
  id: string;
  name: string;
  type: "llm" | "embedding" | "multimodal";
  baseUrl: string;
  apiKey?: string;
  modelName?: string;
  isConnected?: boolean;
  latency?: number;
  lastTestedAt?: Date;
  createdAt: Date;
}

const modelTypeInfo: Record<ModelType, { label: string; icon: typeof Bot; color: string }> = {
  llm: { label: "大语言模型", icon: Brain, color: "text-blue-500 bg-blue-500/10" },
  embedding: { label: "向量模型", icon: Link2, color: "text-purple-500 bg-purple-500/10" },
  multimodal: { label: "多模态模型", icon: Image, color: "text-green-500 bg-green-500/10" },
};

export default function ModelsPage() {
  const { models, addModel, updateModel, deleteModel, testModel, syncModelsFromBackend } = useSettingsStore();

  const [isAddOpen, setIsAddOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<ModelConfig | null>(null);
  const [testingIds, setTestingIds] = useState<Set<string>>(new Set());

  // 页面加载时从后端同步模型
  useEffect(() => {
    syncModelsFromBackend();
  }, [syncModelsFromBackend]);

  const [formData, setFormData] = useState<{
    name: string;
    type: ModelType;
    baseUrl: string;
    modelName: string;
    apiKey: string;
  }>({
    name: "",
    type: "llm",
    baseUrl: "",
    modelName: "",
    apiKey: "",
  });

  const handleOpenAdd = () => {
    setEditingModel(null);
    setFormData({ name: "", type: "llm", baseUrl: "", modelName: "", apiKey: "" });
    setIsAddOpen(true);
  };

  const handleOpenEdit = (model: ModelConfig) => {
    setEditingModel(model);
    setFormData({
      name: model.name,
      type: model.type,
      baseUrl: model.baseUrl,
      modelName: model.modelName || "",
      apiKey: model.apiKey || "",
    });
    setIsAddOpen(true);
  };

  const handleSave = () => {
    if (!formData.name.trim() || !formData.baseUrl.trim() || !formData.modelName.trim()) {
      return;
    }

    if (editingModel) {
      updateModel(editingModel.id, {
        name: formData.name.trim(),
        type: formData.type,
        baseUrl: formData.baseUrl.trim(),
        modelName: formData.modelName.trim(),
        apiKey: formData.apiKey.trim() || undefined,
      });
    } else {
      const newModel: ModelConfig = {
        id: `model-${Date.now()}`,
        name: formData.name.trim(),
        type: formData.type,
        baseUrl: formData.baseUrl.trim(),
        modelName: formData.modelName.trim(),
        apiKey: formData.apiKey.trim() || undefined,
        createdAt: new Date(),
      };
      addModel(newModel);
    }

    setIsAddOpen(false);
  };

  const handleTest = async (model: ModelConfig) => {
    setTestingIds((prev) => new Set(prev).add(model.id));
    await testModel(model.id);
    setTestingIds((prev) => {
      const next = new Set(prev);
      next.delete(model.id);
      return next;
    });
  };

  const typeCount = {
    llm: models.filter((m) => m.type === "llm").length,
    embedding: models.filter((m) => m.type === "embedding").length,
    multimodal: models.filter((m) => m.type === "multimodal").length,
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold flex items-center gap-2">
              <Bot className="h-6 w-6" />
              大模型配置
            </h1>
            <p className="text-muted-foreground mt-1">
              管理 AI 模型连接，支持自定义添加和配置
            </p>
          </div>
          <Button onClick={handleOpenAdd} className="gap-2">
            <Plus className="h-4 w-4" />
            添加模型
          </Button>

          {/* Dialog 使用受控模式 */}
          <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
            <DialogContent className="max-w-lg">
              <DialogHeader>
                <DialogTitle>
                  {editingModel ? "编辑模型" : "添加新模型"}
                </DialogTitle>
                <DialogDescription>
                  配置模型的连接信息，支持 OpenAI 格式的 API
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-4 py-4">
                {/* 模型名称 */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">模型名称</label>
                  <Input
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="例如：GPT-4o、Mistral-7B"
                  />
                </div>

                {/* 模型类型 */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">模型类型</label>
                  <div className="flex gap-2">
                    {(Object.keys(modelTypeInfo) as ModelType[]).map((type) => {
                      const info = modelTypeInfo[type];
                      return (
                        <button
                          key={type}
                          onClick={() => setFormData({ ...formData, type })}
                          className={cn(
                            "flex items-center gap-2 px-4 py-2 rounded-lg border-2 transition-colors flex-1",
                            formData.type === type
                              ? "border-primary bg-primary/5"
                              : "border-border hover:border-primary/50"
                          )}
                        >
                          <info.icon className="h-4 w-4" />
                          <span className="text-sm font-medium">{info.label}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Base URL */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Base URL</label>
                  <Input
                    value={formData.baseUrl}
                    onChange={(e) => setFormData({ ...formData, baseUrl: e.target.value })}
                    placeholder="https://api.openai.com/v1"
                  />
                  <p className="text-xs text-muted-foreground">
                    API 的基础地址，通常以 /v1 结尾
                  </p>
                </div>

                {/* 模型标识 */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">模型标识</label>
                  <Input
                    value={formData.modelName}
                    onChange={(e) => setFormData({ ...formData, modelName: e.target.value })}
                    placeholder="gpt-4o、claude-3-opus"
                  />
                  <p className="text-xs text-muted-foreground">
                    模型的技术标识，用于 API 调用
                  </p>
                </div>

                {/* API Key */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">
                    API Key <span className="text-muted-foreground font-normal">(可选)</span>
                  </label>
                  <Input
                    type="password"
                    value={formData.apiKey}
                    onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
                    placeholder="sk-xxxxxxxxxxxxxxxx"
                  />
                  <p className="text-xs text-muted-foreground">
                    如留空，将使用设置中的全局 API Key
                  </p>
                </div>
              </div>

              <DialogFooter>
                <Button variant="outline" onClick={() => setIsAddOpen(false)}>
                  取消
                </Button>
                <Button onClick={handleSave} disabled={!formData.name || !formData.baseUrl || !formData.modelName}>
                  保存
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        {/* 统计卡片 */}
        <div className="grid grid-cols-3 gap-4">
          {(Object.keys(modelTypeInfo) as ModelType[]).map((type) => {
            const info = modelTypeInfo[type];
            return (
              <Card key={type}>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-muted-foreground">{info.label}</p>
                      <p className="text-2xl font-bold mt-1">{typeCount[type]}</p>
                    </div>
                    <div className={cn("p-3 rounded-lg", info.color)}>
                      <info.icon className="h-5 w-5" />
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* 模型列表 */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">已配置模型</h2>

          {models.length === 0 ? (
            <Card className="p-8 text-center">
              <div className="w-16 h-16 rounded-full bg-muted mx-auto flex items-center justify-center mb-4">
                <Bot className="h-8 w-8 text-muted-foreground" />
              </div>
              <h3 className="text-lg font-medium mb-2">暂无配置模型</h3>
              <p className="text-muted-foreground text-sm mb-4">
                点击上方「添加模型」按钮开始配置你的 AI 模型
              </p>
              <Button onClick={handleOpenAdd} className="gap-2">
                <Plus className="h-4 w-4" />
                添加模型
              </Button>
            </Card>
          ) : (
            <div className="space-y-3">
              {models.map((model) => {
                const typeInfo = modelTypeInfo[model.type];
                const isTesting = testingIds.has(model.id);

                return (
                  <Card key={model.id} className="p-4">
                    <div className="flex items-center gap-4">
                      {/* 图标 */}
                      <div className={cn("p-3 rounded-lg shrink-0", typeInfo.color)}>
                        <typeInfo.icon className="h-5 w-5" />
                      </div>

                      {/* 信息 */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="font-medium">{model.name}</h3>
                          <Badge variant="secondary" className="text-xs">
                            {typeInfo.label}
                          </Badge>
                          {model.isConnected ? (
                            <Badge variant="outline" className="text-xs gap-1 text-green-500 border-green-500/50">
                              <CheckCircle2 className="h-3 w-3" />
                              已连接
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="text-xs gap-1 text-muted-foreground">
                              <AlertCircle className="h-3 w-3" />
                              未连接
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground mt-1 truncate">
                          {model.baseUrl} / {model.modelName}
                        </p>
                      </div>

                      {/* 延迟 */}
                      {model.latency && (
                        <div className="text-right shrink-0">
                          <p className="text-2xl font-bold text-green-500">{model.latency}</p>
                          <p className="text-xs text-muted-foreground">ms</p>
                        </div>
                      )}

                      {/* 操作 */}
                      <div className="flex items-center gap-2 shrink-0">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleTest(model)}
                          disabled={isTesting}
                          className="gap-1"
                        >
                          {isTesting ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Zap className="h-4 w-4" />
                          )}
                          测速
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleOpenEdit(model)}
                          className="gap-1"
                        >
                          <Edit2 className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => deleteModel(model.id)}
                          className="gap-1 text-destructive hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>

                    {/* 详细信息 */}
                    <Separator className="my-4" />
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <span className="w-16">Base URL:</span>
                        <span className="font-mono text-xs truncate">{model.baseUrl}</span>
                      </div>
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <span className="w-16">模型名:</span>
                        <span className="font-mono text-xs">{model.modelName}</span>
                      </div>
                      {model.lastTestedAt && (
                        <div className="flex items-center gap-2 text-muted-foreground col-span-2">
                          <Clock className="h-4 w-4" />
                          <span>上次测试: {new Date(model.lastTestedAt).toLocaleString("zh-CN")}</span>
                        </div>
                      )}
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </div>

        {/* 使用说明 */}
        <Card className="bg-muted/50">
          <CardHeader>
            <CardTitle className="text-base">使用说明</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <p>• <strong>大语言模型 (LLM)</strong>：用于对话生成、内容创作等任务</p>
            <p>• <strong>向量模型 (Embedding)</strong>：用于将文本转为向量，实现语义检索</p>
            <p>• <strong>多模态模型</strong>：支持图像理解、图像生成等任务</p>
            <p>• 支持 OpenAI 格式的 API，可对接 OpenRouter、SiliconFlow 等第三方服务</p>
            <p>• API Key 可以留空，系统将使用全局配置的 Key</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}