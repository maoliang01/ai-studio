import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { UserSettings, APIKeyConfig, ModelConfig } from "@/types";

interface SettingsStore {
  settings: UserSettings;
  apiKeys: APIKeyConfig[];
  models: ModelConfig[];

  // Settings Actions
  setTheme: (theme: UserSettings["theme"]) => void;
  setPrimaryColor: (color: string) => void;

  // API Key Actions
  saveApiKey: (config: APIKeyConfig) => void;
  deleteApiKey: (provider: string) => void;

  // Model Config Actions
  addModel: (model: ModelConfig) => void;
  updateModel: (id: string, updates: Partial<ModelConfig>) => void;
  deleteModel: (id: string) => void;
  testModel: (id: string) => Promise<{ success: boolean; latency?: number; error?: string }>;
}

export const useSettingsStore = create<SettingsStore>()(
  persist(
    (set, get) => ({
      settings: {
        theme: "dark",
        primaryColor: "indigo",
        sidebarCollapsed: false,
      },
      apiKeys: [],
      models: [
        // 默认预置的模型示例
        {
          id: "openai-gpt4o",
          name: "GPT-4o",
          type: "llm",
          baseUrl: "https://api.openai.com/v1",
          apiKey: "",
          modelName: "gpt-4o",
          isConnected: true,
          latency: 320,
          lastTestedAt: new Date(),
          createdAt: new Date(),
        },
        {
          id: "openai-embedding",
          name: "text-embedding-3-small",
          type: "embedding",
          baseUrl: "https://api.openai.com/v1",
          apiKey: "",
          modelName: "text-embedding-3-small",
          isConnected: true,
          latency: 85,
          lastTestedAt: new Date(),
          createdAt: new Date(),
        },
      ],

      setTheme: (theme) =>
        set((state) => ({
          settings: { ...state.settings, theme },
        })),

      setPrimaryColor: (color) =>
        set((state) => ({
          settings: { ...state.settings, primaryColor: color },
        })),

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

      addModel: (model) =>
        set((state) => ({
          models: [...state.models, model],
        })),

      updateModel: (id, updates) =>
        set((state) => ({
          models: state.models.map((m) =>
            m.id === id ? { ...m, ...updates } : m
          ),
        })),

      deleteModel: (id) =>
        set((state) => ({
          models: state.models.filter((m) => m.id !== id),
        })),

      testModel: async (id) => {
        const model = get().models.find((m) => m.id === id);
        if (!model) {
          return { success: false, error: "模型不存在" };
        }

        // 模拟测速延迟
        await new Promise((resolve) => setTimeout(resolve, 800 + Math.random() * 1200));

        // 模拟：90%成功率
        const success = Math.random() > 0.1;
        const latency = Math.floor(150 + Math.random() * 400);

        set((state) => ({
          models: state.models.map((m) =>
            m.id === id
              ? {
                  ...m,
                  isConnected: success,
                  latency: success ? latency : undefined,
                  lastTestedAt: new Date(),
                }
              : m
          ),
        }));

        return success
          ? { success: true, latency }
          : { success: false, error: "连接超时" };
      },
    }),
    {
      name: "ai-studio-settings",
    }
  )
);