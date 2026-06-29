"use client";

import { useState, useEffect } from "react";
import { useSettingsStore } from "@/stores/settings-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  Globe,
  Plus,
  Pencil,
  Trash2,
  ExternalLink,
} from "lucide-react";
import type { WebsiteCategory, ScrapeSource } from "@/types";

export default function ScrapeSettingsPage() {
  const {
    scrapeSources,
    addScrapeSource,
    updateScrapeSource,
    deleteScrapeSource,
    toggleScrapeSource,
    syncFromBackend,
    isLoading,
  } = useSettingsStore();

  // 组件挂载时从后端同步数据
  useEffect(() => {
    syncFromBackend();
  }, [syncFromBackend]);

  const [scrapeDialogOpen, setScrapeDialogOpen] = useState(false);
  const [editingScrapeSource, setEditingScrapeSource] = useState<ScrapeSource | null>(null);
  const [scrapeForm, setScrapeForm] = useState({
    name: "",
    url: "",
    category: "business" as WebsiteCategory,
    description: "",
    isEnabled: true,
  });

  const handleOpenScrapeDialog = (source?: ScrapeSource) => {
    if (source) {
      setEditingScrapeSource(source);
      setScrapeForm({
        name: source.name,
        url: source.url,
        category: source.category,
        description: source.description || "",
        isEnabled: source.isEnabled,
      });
    } else {
      setEditingScrapeSource(null);
      setScrapeForm({
        name: "",
        url: "",
        category: "business",
        description: "",
        isEnabled: true,
      });
    }
    setScrapeDialogOpen(true);
  };

  const handleSaveScrapeSource = () => {
    if (!scrapeForm.name.trim() || !scrapeForm.url.trim()) return;

    if (editingScrapeSource) {
      updateScrapeSource(editingScrapeSource.id, scrapeForm);
    } else {
      addScrapeSource(scrapeForm);
    }
    setScrapeDialogOpen(false);
  };

  const getCategoryLabel = (category: WebsiteCategory) => {
    const labels: Record<WebsiteCategory, string> = {
      government: "党政类",
      business: "商务类",
      academic: "学术类",
    };
    return labels[category];
  };

  const getCategoryColors = (category: WebsiteCategory) => {
    const colors: Record<WebsiteCategory, string> = {
      government: "text-red-600 border-red-200 bg-red-50",
      business: "text-blue-600 border-blue-200 bg-blue-50",
      academic: "text-green-600 border-green-200 bg-green-50",
    };
    return colors[category];
  };

  // 统计各类型数量
  const stats = {
    total: scrapeSources.length,
    government: scrapeSources.filter((s) => s.category === "government").length,
    business: scrapeSources.filter((s) => s.category === "business").length,
    academic: scrapeSources.filter((s) => s.category === "academic").length,
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        {/* 页面标题 */}
        <div>
          <h1 className="text-2xl font-semibold mb-2">网页爬取配置</h1>
          <p className="text-muted-foreground">管理要爬取的网页来源，支持分类管理</p>
        </div>

        {/* 统计卡片 */}
        <div className="grid grid-cols-4 gap-4">
          <Card className="p-4 text-center">
            <p className="text-2xl font-bold">{stats.total}</p>
            <p className="text-xs text-muted-foreground">全部</p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-2xl font-bold text-red-600">{stats.government}</p>
            <p className="text-xs text-muted-foreground">党政类</p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-2xl font-bold text-blue-600">{stats.business}</p>
            <p className="text-xs text-muted-foreground">商务类</p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-2xl font-bold text-green-600">{stats.academic}</p>
            <p className="text-xs text-muted-foreground">学术类</p>
          </Card>
        </div>

        {/* 爬取源列表 */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <Globe className="h-5 w-5 text-primary" />
              </div>
              <div>
                <h2 className="text-lg font-semibold">网页来源</h2>
                <p className="text-sm text-muted-foreground">
                  配置要爬取的网页列表
                </p>
              </div>
            </div>
            <Button onClick={() => handleOpenScrapeDialog()} className="gap-2">
              <Plus className="h-4 w-4" />
              添加网页
            </Button>
          </div>

          {scrapeSources.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Globe className="h-16 w-16 mx-auto mb-4 opacity-50" />
              <p className="mb-1 text-lg">暂无配置的网页来源</p>
              <p className="text-sm">点击上方按钮添加要爬取的网页</p>
            </div>
          ) : (
            <div className="space-y-3">
              {scrapeSources.map((source) => (
                <div
                  key={source.id}
                  className="flex items-center gap-4 p-4 rounded-lg bg-muted/50 hover:bg-muted transition-colors"
                >
                  <Switch
                    checked={source.isEnabled}
                    onCheckedChange={() => toggleScrapeSource(source.id)}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium">{source.name}</span>
                      <Badge
                        variant="outline"
                        className={getCategoryColors(source.category)}
                      >
                        {getCategoryLabel(source.category)}
                      </Badge>
                    </div>
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-muted-foreground hover:text-primary flex items-center gap-1 truncate"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                      {source.url}
                    </a>
                    {source.description && (
                      <p className="text-xs text-muted-foreground mt-2 line-clamp-1">
                        {source.description}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleOpenScrapeDialog(source)}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => deleteScrapeSource(source.id)}
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* 爬取源配置 Dialog */}
        <Dialog open={scrapeDialogOpen} onOpenChange={setScrapeDialogOpen}>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle>
                {editingScrapeSource ? "编辑网页来源" : "添加网页来源"}
              </DialogTitle>
              <DialogDescription>
                配置要爬取的网页信息，包括名称、地址和分类
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-4">
              {/* 网页名称 */}
              <div className="space-y-2">
                <Label htmlFor="scrape-name">
                  网页名称 <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="scrape-name"
                  value={scrapeForm.name}
                  onChange={(e) =>
                    setScrapeForm({ ...scrapeForm, name: e.target.value })
                  }
                  placeholder="例如：某政府官网"
                />
              </div>

              {/* 网页 URL */}
              <div className="space-y-2">
                <Label htmlFor="scrape-url">
                  网页地址 <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="scrape-url"
                  value={scrapeForm.url}
                  onChange={(e) =>
                    setScrapeForm({ ...scrapeForm, url: e.target.value })
                  }
                  placeholder="https://example.com"
                  type="url"
                />
              </div>

              {/* 网页种类 */}
              <div className="space-y-2">
                <Label htmlFor="scrape-category">网页种类</Label>
                <Select
                  value={scrapeForm.category}
                  onValueChange={(value) =>
                    setScrapeForm({
                      ...scrapeForm,
                      category: value as WebsiteCategory,
                    })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="选择网页种类" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="government">党政类</SelectItem>
                    <SelectItem value="business">商务类</SelectItem>
                    <SelectItem value="academic">学术类</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* 描述 */}
              <div className="space-y-2">
                <Label htmlFor="scrape-description">描述（可选）</Label>
                <Textarea
                  id="scrape-description"
                  value={scrapeForm.description}
                  onChange={(e) =>
                    setScrapeForm({ ...scrapeForm, description: e.target.value })
                  }
                  placeholder="简要描述这个网页来源..."
                  rows={2}
                />
              </div>

              {/* 启用开关 */}
              <div className="flex items-center gap-2">
                <Switch
                  checked={scrapeForm.isEnabled}
                  onCheckedChange={(checked) =>
                    setScrapeForm({ ...scrapeForm, isEnabled: checked })
                  }
                />
                <Label className="cursor-pointer">默认启用爬取</Label>
              </div>
            </div>

            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setScrapeDialogOpen(false)}
              >
                取消
              </Button>
              <Button
                onClick={handleSaveScrapeSource}
                disabled={!scrapeForm.name.trim() || !scrapeForm.url.trim()}
              >
                {editingScrapeSource ? "保存" : "添加"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}