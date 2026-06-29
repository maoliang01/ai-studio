import { create } from "zustand";
import { persist } from "zustand/middleware";
import { subscribeWithSelector } from "zustand/middleware";
import type { ScrapeSource, ModelInfo } from "@/types";

// API Key 配置（前端专用）
interface APIKeyConfig {
  provider: string;
  apiKey: string;
  baseUrl?: string;
  isValid?: boolean;
}

// 模型配置（前端专用）
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

// 用户设置类型
interface UserSettings {
  theme: "light" | "dark" | "system";
  primaryColor: string;
  scrapeSources: ScrapeSource[];
}

interface SettingsStore {
  settings: UserSettings;
  apiKeys: APIKeyConfig[];
  models: ModelConfig[];
  scrapeSources: ScrapeSource[];
  isLoading: boolean;
  isBackendSynced: boolean;

  // Settings Actions
  setTheme: (theme: UserSettings["theme"]) => void;
  setPrimaryColor: (color: string) => void;
  syncFromBackend: () => Promise<void>;

  // API Key Actions
  saveApiKey: (config: APIKeyConfig) => void;
  deleteApiKey: (provider: string) => void;

  // Model Config Actions
  addModel: (model: ModelConfig) => void;
  updateModel: (id: string, updates: Partial<ModelConfig>) => void;
  deleteModel: (id: string) => void;
  testModel: (id: string) => Promise<{ success: boolean; latency?: number; error?: string }>;

  // Scrape Source Actions
  addScrapeSource: (source: Omit<ScrapeSource, "id" | "createdAt" | "updatedAt">) => void;
  updateScrapeSource: (id: string, updates: Partial<ScrapeSource>) => void;
  deleteScrapeSource: (id: string) => void;
  toggleScrapeSource: (id: string) => void;

  // 模型同步（从后端）
  syncModelsFromBackend: () => Promise<void>;
}

export const useSettingsStore = create<SettingsStore>()(
  subscribeWithSelector(
    persist(
      (set, get) => ({
      settings: {
        theme: "dark",
        primaryColor: "indigo",
        scrapeSources: [],
      },
      apiKeys: [],
      models: [],  // 不从 localStorage 加载，每次从后端获取
      scrapeSources: [],  // 不从 localStorage 加载，每次从后端获取
      isLoading: false,
      isBackendSynced: false,

      setTheme: (theme) =>
        set((state) => ({
          settings: { ...state.settings, theme },
        })),

      setPrimaryColor: (color) =>
        set((state) => ({
          settings: { ...state.settings, primaryColor: color },
        })),

      // 从后端同步配置
      syncFromBackend: async () => {
        set({ isLoading: true });
        try {
          const res = await fetch("/api/settings/scrape");
          if (res.ok) {
            const data = await res.json();
            // 将后端数据转换为前端格式
            const scrapeSources: ScrapeSource[] = data.map((source: any) => ({
              id: source.id,
              name: source.name,
              url: source.url,
              category: source.category,
              description: source.description,
              isEnabled: source.is_enabled,
              createdAt: new Date(source.created_at),
              updatedAt: new Date(source.updated_at),
            }));
            set({ scrapeSources, isBackendSynced: true });
          }
        } catch (error) {
          console.error("同步失败:", error);
        } finally {
          set({ isLoading: false });
        }
      },

      saveApiKey: (config) =>
        set((state) => {
          const existing = state.apiKeys.findIndex(
            (k) => k.provider === config.provider
          );
          if (existing >= 0) {
            const updated = [...state.apiKeys];
            updated[existing] = config;
            return { apiKeys: updated };
          }
          return { apiKeys: [...state.apiKeys, config] };
        }),

      deleteApiKey: (provider) =>
        set((state) => ({
          apiKeys: state.apiKeys.filter((k) => k.provider !== provider),
        })),

      // 从后端同步模型配置（合并现有数据）
      syncModelsFromBackend: async () => {
        try {
          const res = await fetch("/api/models");
          if (res.ok) {
            const data = await res.json();
            const currentModels = get().models;

            // 将后端数据转换为前端格式，保留本地测试结果
            const models: ModelConfig[] = data.map((model: any) => {
              // 查找本地已有的模型，保留测试结果
              const localModel = currentModels.find((m) => m.id === model.id);
              return {
                id: model.id,
                name: model.name,
                type: model.type,
                baseUrl: model.base_url,
                apiKey: model.api_key,
                modelName: model.model_name,
                // 优先使用后端最新值，否则保留本地值
                isConnected: model.is_connected ?? localModel?.isConnected,
                latency: model.latency ?? localModel?.latency,
                lastTestedAt: model.last_tested_at
                  ? new Date(model.last_tested_at)
                  : localModel?.lastTestedAt,
                createdAt: localModel?.createdAt || new Date(),
              };
            });
            set({ models });
          }
        } catch (error) {
          console.error("同步模型失败:", error);
        }
      },

      addModel: async (model) => {
        try {
          const res = await fetch("/api/models", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              name: model.name,
              type: model.type,
              base_url: model.baseUrl,
              api_key: model.apiKey,
              model_name: model.modelName,
            }),
          });
          if (res.ok) {
            await get().syncModelsFromBackend();
          }
        } catch (error) {
          console.error("添加模型失败:", error);
        }
      },

      updateModel: async (id, updates) => {
        try {
          const res = await fetch(`/api/models?id=${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              name: updates.name,
              type: updates.type,
              base_url: updates.baseUrl,
              api_key: updates.apiKey,
              model_name: updates.modelName,
            }),
          });
          if (res.ok) {
            await get().syncModelsFromBackend();
          }
        } catch (error) {
          console.error("更新模型失败:", error);
        }
      },

      deleteModel: async (id) => {
        try {
          const res = await fetch(`/api/models?id=${id}`, {
            method: "DELETE",
          });
          if (res.ok) {
            set((state) => ({
              models: state.models.filter((m) => m.id !== id),
            }));
          }
        } catch (error) {
          console.error("删除模型失败:", error);
        }
      },

      testModel: async (id) => {
        try {
          const res = await fetch(`/api/models/${id}/test`, {
            method: "POST",
          });
          if (!res.ok) {
            const error = await res.json().catch(() => ({ error: "测试失败" }));
            return { success: false, error: error.detail || error.error || "测试失败" };
          }
          const result = await res.json();
          set((state) => ({
            models: state.models.map((m) =>
              m.id === id
                ? {
                    ...m,
                    isConnected: result.success,
                    latency: result.latency,
                    lastTestedAt: new Date(),
                  }
                : m
            ),
          }));
          return { success: result.success, latency: result.latency, error: result.error };
        } catch (error) {
          console.error("测试模型失败:", error);
          return { success: false, error: "网络错误" };
        }
      },

      // Scrape Source Actions - 现在调用后端 API
      addScrapeSource: async (source) => {
        try {
          const res = await fetch("/api/settings/scrape", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              name: source.name,
              url: source.url,
              category: source.category,
              description: source.description,
              is_enabled: source.isEnabled,
            }),
          });
          if (res.ok) {
            // 重新从后端获取最新数据
            await get().syncFromBackend();
          }
        } catch (error) {
          console.error("添加爬取源失败:", error);
        }
      },

      updateScrapeSource: async (id, updates) => {
        try {
          const res = await fetch(`/api/settings/scrape?id=${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              name: updates.name,
              url: updates.url,
              category: updates.category,
              description: updates.description,
              is_enabled: updates.isEnabled,
            }),
          });
          if (res.ok) {
            await get().syncFromBackend();
          }
        } catch (error) {
          console.error("更新爬取源失败:", error);
        }
      },

      deleteScrapeSource: async (id) => {
        try {
          const res = await fetch(`/api/settings/scrape?id=${id}`, {
            method: "DELETE",
          });
          if (res.ok) {
            set((state) => ({
              scrapeSources: state.scrapeSources.filter((s) => s.id !== id),
            }));
          }
        } catch (error) {
          console.error("删除爬取源失败:", error);
        }
      },

      toggleScrapeSource: async (id) => {
        try {
          const res = await fetch(`/api/settings/scrape/${id}/toggle`, {
            method: "POST",
          });
          if (res.ok) {
            set((state) => ({
              scrapeSources: state.scrapeSources.map((s) =>
                s.id === id ? { ...s, isEnabled: !s.isEnabled } : s
              ),
            }));
          }
        } catch (error) {
          console.error("切换状态失败:", error);
        }
      },
    }),
    {
      name: "ai-studio-settings",
      // 只持久化个人设置，不持久化共享配置（模型、爬取源）
      partialize: (state) => ({
        settings: state.settings,
        apiKeys: state.apiKeys,
        // 排除 models 和 scrapeSources - 这些从后端同步
      }),
    })
  )
);