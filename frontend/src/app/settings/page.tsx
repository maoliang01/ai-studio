"use client";

import Link from "next/link";
import { useState } from "react";
import { useSettingsStore } from "@/stores/settings-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  Key,
  Palette,
  Keyboard,
  Database,
  Sun,
  Moon,
  Monitor,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Eye,
  EyeOff,
  Bot,
} from "lucide-react";
import { cn } from "@/lib/utils";

// Bot 重命名为 BotIcon 避免与类型冲突
const BotIcon = Bot;

const colorOptions = [
  { id: "indigo", name: "靛蓝", color: "bg-indigo-500" },
  { id: "violet", name: "蓝紫", color: "bg-violet-500" },
  { id: "blue", name: "蓝色", color: "bg-blue-500" },
  { id: "cyan", name: "青色", color: "bg-cyan-500" },
  { id: "emerald", name: "绿色", color: "bg-emerald-500" },
];

export default function SettingsPage() {
  const { settings, setTheme, setPrimaryColor, apiKeys, saveApiKey, deleteApiKey } =
    useSettingsStore();

  const [showApiKeys, setShowApiKeys] = useState<Record<string, boolean>>({});
  const [apiKeyInputs, setApiKeyInputs] = useState<Record<string, { key: string; baseUrl: string }>>({});
  const [testingApiKey, setTestingApiKey] = useState<string | null>(null);
  const [apiKeyStatus, setApiKeyStatus] = useState<Record<string, "valid" | "invalid" | null>>({});

  const toggleShowApiKey = (provider: string) => {
    setShowApiKeys((prev) => ({ ...prev, [provider]: !prev[provider] }));
  };

  const handleSaveApiKey = (provider: string) => {
    const input = apiKeyInputs[provider];
    if (!input?.key?.trim()) return;

    saveApiKey({
      provider,
      apiKey: input.key.trim(),
      baseUrl: input.baseUrl?.trim() || undefined,
    });
    setApiKeyInputs((prev) => ({ ...prev, [provider]: { key: "", baseUrl: "" } }));
  };

  const handleTestApiKey = async (provider: string) => {
    setTestingApiKey(provider);
    // 模拟测试
    await new Promise((resolve) => setTimeout(resolve, 1500));
    const isValid = Math.random() > 0.3;
    setApiKeyStatus((prev) => ({ ...prev, [provider]: isValid ? "valid" : "invalid" }));
    setTestingApiKey(null);
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-8">
        <div>
          <h1 className="text-2xl font-semibold mb-2">设置</h1>
          <p className="text-muted-foreground">配置 AI Studio 的各项功能</p>
        </div>

        {/* API 配置 */}
        <Card className="p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <Key className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h2 className="text-lg font-semibold">API 密钥配置</h2>
              <p className="text-sm text-muted-foreground">
                配置你从各服务商获取的 API 密钥
              </p>
            </div>
          </div>

          <div className="space-y-6">
            {/* OpenAI */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-base font-medium">OpenAI API Key</Label>
                  <p className="text-sm text-muted-foreground">
                    用于调用 GPT 系列模型
                  </p>
                </div>
                {apiKeys.find((k) => k.provider === "openai") && (
                  <Badge variant="secondary" className="gap-1">
                    <CheckCircle2 className="h-3 w-3 text-green-500" />
                    已配置
                  </Badge>
                )}
              </div>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Input
                    type={showApiKeys["openai"] ? "text" : "password"}
                    value={apiKeyInputs["openai"]?.key || ""}
                    onChange={(e) =>
                      setApiKeyInputs((prev) => ({
                        ...prev,
                        openai: { ...prev["openai"], key: e.target.value },
                      }))
                    }
                    placeholder="sk-xxxxxxxxxxxxxxxx"
                    className="pr-10"
                  />
                  <button
                    onClick={() => toggleShowApiKey("openai")}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showApiKeys["openai"] ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
                <Button onClick={() => handleSaveApiKey("openai")}>保存</Button>
                {apiKeys.find((k) => k.provider === "openai") && (
                  <Button
                    variant="outline"
                    onClick={() => handleTestApiKey("openai")}
                    disabled={testingApiKey === "openai"}
                  >
                    {testingApiKey === "openai" ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : apiKeyStatus["openai"] === "valid" ? (
                      <CheckCircle2 className="h-4 w-4 text-green-500" />
                    ) : apiKeyStatus["openai"] === "invalid" ? (
                      <AlertCircle className="h-4 w-4 text-red-500" />
                    ) : (
                      "测试连接"
                    )}
                  </Button>
                )}
              </div>
            </div>

            <Separator />

            {/* Anthropic */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-base font-medium">Anthropic API Key</Label>
                  <p className="text-sm text-muted-foreground">
                    用于调用 Claude 系列模型
                  </p>
                </div>
                {apiKeys.find((k) => k.provider === "anthropic") && (
                  <Badge variant="secondary" className="gap-1">
                    <CheckCircle2 className="h-3 w-3 text-green-500" />
                    已配置
                  </Badge>
                )}
              </div>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Input
                    type={showApiKeys["anthropic"] ? "text" : "password"}
                    value={apiKeyInputs["anthropic"]?.key || ""}
                    onChange={(e) =>
                      setApiKeyInputs((prev) => ({
                        ...prev,
                        anthropic: { ...prev["anthropic"], key: e.target.value },
                      }))
                    }
                    placeholder="sk-ant-xxxxxxxxxxxxxxxx"
                    className="pr-10"
                  />
                  <button
                    onClick={() => toggleShowApiKey("anthropic")}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showApiKeys["anthropic"] ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
                <Button onClick={() => handleSaveApiKey("anthropic")}>保存</Button>
                {apiKeys.find((k) => k.provider === "anthropic") && (
                  <Button
                    variant="outline"
                    onClick={() => handleTestApiKey("anthropic")}
                    disabled={testingApiKey === "anthropic"}
                  >
                    {testingApiKey === "anthropic" ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      "测试连接"
                    )}
                  </Button>
                )}
              </div>
            </div>

            <Separator />

            {/* 自定义端点 */}
            <div className="space-y-3">
              <div>
                <Label className="text-base font-medium">自定义端点</Label>
                <p className="text-sm text-muted-foreground">
                  用于兼容 OpenAI 格式的第三方 API（如 OpenRouter、SiliconFlow 等）
                </p>
              </div>
              <div className="grid gap-3">
                <Input
                  value={apiKeyInputs["custom"]?.baseUrl || ""}
                  onChange={(e) =>
                    setApiKeyInputs((prev) => ({
                      ...prev,
                      custom: { ...prev["custom"], baseUrl: e.target.value },
                    }))
                  }
                  placeholder="https://api.openrouter.ai/v1"
                />
                <div className="flex gap-2">
                  <Input
                    type={showApiKeys["custom"] ? "text" : "password"}
                    value={apiKeyInputs["custom"]?.key || ""}
                    onChange={(e) =>
                      setApiKeyInputs((prev) => ({
                        ...prev,
                        custom: { ...prev["custom"], key: e.target.value },
                      }))
                    }
                    placeholder="API Key"
                    className="pr-10"
                  />
                  <button
                    onClick={() => toggleShowApiKey("custom")}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showApiKeys["custom"] ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                  <Button onClick={() => handleSaveApiKey("custom")}>保存</Button>
                </div>
              </div>
            </div>
          </div>
        </Card>

        {/* 主题设置 */}
        <Card className="p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <Palette className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h2 className="text-lg font-semibold">外观设置</h2>
              <p className="text-sm text-muted-foreground">自定义界面外观和颜色</p>
            </div>
          </div>

          <div className="space-y-6">
            {/* 外观模式 */}
            <div>
              <Label className="text-base font-medium mb-3 block">外观模式</Label>
              <div className="flex gap-3">
                {[
                  { value: "light", icon: Sun, label: "浅色" },
                  { value: "dark", icon: Moon, label: "深色" },
                  { value: "system", icon: Monitor, label: "跟随系统" },
                ].map((option) => (
                  <button
                    key={option.value}
                    onClick={() => setTheme(option.value as typeof settings.theme)}
                    className={cn(
                      "flex flex-1 flex-col items-center gap-2 p-4 rounded-lg border-2 transition-colors",
                      settings.theme === option.value
                        ? "border-primary bg-primary/5"
                        : "border-border hover:border-primary/50"
                    )}
                  >
                    <option.icon className="h-6 w-6" />
                    <span className="text-sm font-medium">{option.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <Separator />

            {/* 主题色 */}
            <div>
              <Label className="text-base font-medium mb-3 block">主题色</Label>
              <div className="flex flex-wrap gap-3">
                {colorOptions.map((option) => (
                  <button
                    key={option.id}
                    onClick={() => setPrimaryColor(option.id)}
                    className={cn(
                      "flex items-center gap-2 px-4 py-2 rounded-lg border-2 transition-colors",
                      settings.primaryColor === option.id
                        ? "border-primary bg-primary/5"
                        : "border-border hover:border-primary/50"
                    )}
                  >
                    <span className={cn("h-4 w-4 rounded-full", option.color)} />
                    <span className="text-sm font-medium">{option.name}</span>
                  </button>
                ))}
              </div>
            </div>

            <Separator />

            {/* 预览 */}
            <div>
              <Label className="text-base font-medium mb-3 block">预览</Label>
              <Card className="p-4 bg-muted/50">
                <div className="flex items-center gap-4 mb-4">
                  <div
                    className="h-2 w-16 rounded-full"
                    style={{
                      backgroundColor:
                        settings.primaryColor === "indigo"
                          ? "#6366F1"
                          : settings.primaryColor === "violet"
                            ? "#7C3AED"
                            : settings.primaryColor === "blue"
                              ? "#3B82F6"
                              : settings.primaryColor === "cyan"
                                ? "#06B6D4"
                                : "#10B981",
                    }}
                  />
                  <span className="text-sm font-medium">AI Studio</span>
                </div>
                <div className="space-y-2">
                  <div className="h-3 w-3/4 rounded bg-muted-foreground/20" />
                  <div className="h-3 w-1/2 rounded bg-muted-foreground/20" />
                </div>
                <Button
                  size="sm"
                  className="mt-4"
                  style={{
                    backgroundColor:
                      settings.primaryColor === "indigo"
                        ? "#6366F1"
                        : settings.primaryColor === "violet"
                          ? "#7C3AED"
                          : settings.primaryColor === "blue"
                            ? "#3B82F6"
                            : settings.primaryColor === "cyan"
                              ? "#06B6D4"
                              : "#10B981",
                  }}
                >
                  按钮
                </Button>
              </Card>
            </div>
          </div>
        </Card>

        {/* 模型配置入口 */}
        <Card className="p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <BotIcon className="h-5 w-5 text-primary" />
            </div>
            <div className="flex-1">
              <h2 className="text-lg font-semibold">大模型配置</h2>
              <p className="text-sm text-muted-foreground">
                管理 AI 模型连接，支持添加自定义模型和测速
              </p>
            </div>
            <Link
              href="/settings/models"
              className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium border border-input background-transparent hover:bg-accent hover:text-accent-foreground h-9 px-4 py-2"
            >
              管理模型
            </Link>
          </div>

          <div className="grid grid-cols-3 gap-4">
            {[
              { type: "llm", label: "大语言模型", count: 1 },
              { type: "embedding", label: "向量模型", count: 1 },
              { type: "multimodal", label: "多模态模型", count: 0 },
            ].map((item) => (
              <div key={item.type} className="p-3 rounded-lg bg-muted/50 text-center">
                <p className="text-2xl font-bold">{item.count}</p>
                <p className="text-xs text-muted-foreground">{item.label}</p>
              </div>
            ))}
          </div>
        </Card>

        {/* 快捷键设置 */}
        <Card className="p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <Keyboard className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h2 className="text-lg font-semibold">键盘快捷键</h2>
              <p className="text-sm text-muted-foreground">常用操作的快捷键</p>
            </div>
          </div>

          <div className="space-y-3">
            {[
              { action: "新建对话", keys: ["Ctrl", "N"] },
              { action: "搜索", keys: ["Ctrl", "K"] },
              { action: "发送消息", keys: ["Enter"] },
              { action: "换行", keys: ["Shift", "Enter"] },
              { action: "停止生成", keys: ["Esc"] },
            ].map((shortcut) => (
              <div
                key={shortcut.action}
                className="flex items-center justify-between py-2"
              >
                <span className="text-sm">{shortcut.action}</span>
                <div className="flex gap-1">
                  {shortcut.keys.map((key, i) => (
                    <kbd
                      key={i}
                      className="px-2 py-1 text-xs font-medium bg-muted rounded border"
                    >
                      {key}
                    </kbd>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* 数据管理 */}
        <Card className="p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <Database className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h2 className="text-lg font-semibold">数据管理</h2>
              <p className="text-sm text-muted-foreground">管理本地存储的数据</p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">对话历史</p>
                <p className="text-sm text-muted-foreground">共 12 条对话记录</p>
              </div>
              <Button variant="outline" size="sm">
                清除
              </Button>
            </div>

            <Separator />

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">知识库</p>
                <p className="text-sm text-muted-foreground">共 3 个文档，125 个块</p>
              </div>
              <Button variant="outline" size="sm">
                清除
              </Button>
            </div>

            <Separator />

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">提示词模板</p>
                <p className="text-sm text-muted-foreground">共 24 个模板</p>
              </div>
              <Button variant="outline" size="sm">
                清除
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}