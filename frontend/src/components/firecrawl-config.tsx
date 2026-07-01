"use client";

import { useEffect, useState } from "react";
import { useSettingsStore } from "@/stores/settings-store";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import {
  Server,
  Globe,
  Key,
  CheckCircle,
  XCircle,
  RefreshCw,
  ExternalLink,
} from "lucide-react";

export function FirecrawlConfig() {
  const {
    firecrawlConfig,
    firecrawlStatus,
    syncFirecrawlConfig,
    updateFirecrawlConfig,
    checkFirecrawlStatus,
  } = useSettingsStore();

  const [isChecking, setIsChecking] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [localUrl, setLocalUrl] = useState(firecrawlConfig.localUrl);
  const [localApiKey, setLocalApiKey] = useState(firecrawlConfig.apiKey);

  // 初始化时同步配置和状态
  useEffect(() => {
    syncFirecrawlConfig();
    checkFirecrawlStatus();

    // 每 30 秒检查一次状态
    const interval = setInterval(checkFirecrawlStatus, 30000);
    return () => clearInterval(interval);
  }, [syncFirecrawlConfig, checkFirecrawlStatus]);

  // 同步本地 state
  useEffect(() => {
    setLocalUrl(firecrawlConfig.localUrl);
    setLocalApiKey(firecrawlConfig.apiKey);
  }, [firecrawlConfig]);

  const handleCheckStatus = async () => {
    setIsChecking(true);
    await checkFirecrawlStatus();
    setIsChecking(false);
  };

  const handleSaveConfig = async () => {
    setIsSaving(true);
    await updateFirecrawlConfig({
      localUrl,
      apiKey: localApiKey,
    });
    setIsSaving(false);
  };

  const handleToggleUseLocal = async (checked: boolean) => {
    await updateFirecrawlConfig({ useLocal: checked });
  };

  return (
    <Card className="p-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
          <Server className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h2 className="text-lg font-semibold">Firecrawl 网页爬取</h2>
          <p className="text-sm text-muted-foreground">配置本地或远程 Firecrawl 服务</p>
        </div>
      </div>

      <div className="space-y-6">
        {/* 服务状态 */}
        <div className="flex items-center justify-between p-4 rounded-lg bg-muted/50">
          <div className="flex items-center gap-3">
            {firecrawlStatus.isRunning ? (
              <CheckCircle className="h-5 w-5 text-green-500" />
            ) : (
              <XCircle className="h-5 w-5 text-red-500" />
            )}
            <div>
              <p className="font-medium">
                {firecrawlStatus.isRunning ? "服务运行中" : "服务未运行"}
              </p>
              <p className="text-sm text-muted-foreground">
                {firecrawlStatus.localUrl}
                {firecrawlStatus.version && ` · v${firecrawlStatus.version}`}
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleCheckStatus}
            disabled={isChecking}
          >
            <RefreshCw className={cn("h-4 w-4 mr-1", isChecking && "animate-spin")} />
            {isChecking ? "检查中..." : "检查状态"}
          </Button>
        </div>

        <Separator />

        {/* 使用本地服务开关 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Globe className="h-5 w-5 text-muted-foreground" />
            <div>
              <Label className="font-medium">使用本地服务</Label>
              <p className="text-sm text-muted-foreground">
                使用本地部署的 Firecrawl 而非远程 API
              </p>
            </div>
          </div>
          <Switch
            checked={firecrawlConfig.useLocal}
            onCheckedChange={handleToggleUseLocal}
          />
        </div>

        {firecrawlConfig.useLocal && (
          <>
            <Separator />

            {/* 本地服务地址 */}
            <div className="space-y-2">
              <Label htmlFor="localUrl" className="flex items-center gap-2">
                <Server className="h-4 w-4" />
                本地服务地址
              </Label>
              <Input
                id="localUrl"
                value={localUrl}
                onChange={(e) => setLocalUrl(e.target.value)}
                placeholder="http://localhost:3002"
              />
              <p className="text-xs text-muted-foreground">
                默认地址: http://localhost:3002
              </p>
            </div>

            {/* API Key */}
            <div className="space-y-2">
              <Label htmlFor="apiKey" className="flex items-center gap-2">
                <Key className="h-4 w-4" />
                API Key
              </Label>
              <Input
                id="apiKey"
                value={localApiKey}
                onChange={(e) => setLocalApiKey(e.target.value)}
                placeholder="local"
              />
              <p className="text-xs text-muted-foreground">
                本地部署可使用 "local" 作为 API Key
              </p>
            </div>

            <Button
              onClick={handleSaveConfig}
              disabled={isSaving}
              className="w-full"
            >
              {isSaving ? "保存中..." : "保存配置"}
            </Button>

            {!firecrawlStatus.isRunning && (
              <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/20">
                <p className="text-sm text-amber-600 dark:text-amber-400 mb-2">
                  💡 服务未启动？请按照以下步骤启动本地 Firecrawl：
                </p>
                <ol className="text-xs text-muted-foreground space-y-1 list-decimal list-inside">
                  <li>打开终端</li>
                  <li>运行: <code className="bg-muted px-1 rounded">cd /tmp/firecrawl && sudo docker compose up -d</code></li>
                  <li>或运行: <code className="bg-muted px-1 rounded">/home/aircas/AI/AI Studio/firecrawl-start.sh</code></li>
                  <li>等待约 10 秒后点击"检查状态"</li>
                </ol>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-3"
                  onClick={() => window.open("http://localhost:3002/docs", "_blank")}
                >
                  <ExternalLink className="h-4 w-4 mr-1" />
                  打开 API 文档
                </Button>
              </div>
            )}
          </>
        )}

        {!firecrawlConfig.useLocal && (
          <div className="p-4 rounded-lg bg-muted/50">
            <p className="text-sm text-muted-foreground">
              目前使用远程 Firecrawl API ({firecrawlConfig.useLocal ? "本地" : "云端"})
            </p>
          </div>
        )}
      </div>
    </Card>
  );
}