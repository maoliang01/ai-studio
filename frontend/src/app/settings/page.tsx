"use client";

import Link from "next/link";
import { useState } from "react";
import { useSettingsStore } from "@/stores/settings-store";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Label } from "@/components/ui/label";
import {
  Palette,
  Sun,
  Moon,
  Monitor,
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
  const {
    settings,
    setTheme,
    setPrimaryColor,
  } = useSettingsStore();

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-8">
        <div>
          <h1 className="text-2xl font-semibold mb-2">设置</h1>
          <p className="text-muted-foreground">配置 AI Studio 的各项功能</p>
        </div>

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
      </div>
    </div>
  );
}