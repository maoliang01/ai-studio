import { create } from "zustand";
import { subscribeWithSelector } from "zustand/middleware";
import type { ChatSession, Message, ModelConfigAPI } from "@/types";
import { sendChat, streamChat } from "@/lib/api";
import { useSettingsStore } from "./settings-store";

// 模型配置类型（内部使用，camelCase）
interface ModelConfig {
  id: string;
  name: string;
  type: string;
  baseUrl: string;
  apiKey?: string;
  modelName?: string;
}

const API_BASE = "/api";  // 使用同源 API 代理

interface ModelOption {
  id: string;
  name: string;
  provider?: string;
  isFavorite?: boolean;
}

interface ChatStore {
  sessions: ChatSession[];
  currentSessionId: string | null;
  models: ModelOption[];
  selectedModel: string;
  isStreaming: boolean;
  isLoading: boolean;
  error: string | null;
  abortController: AbortController | null;
  isInitialized: boolean;

  // Actions
  setCurrentSession: (id: string | null) => void;
  addSession: () => void;
  deleteSession: (id: string) => void;
  addMessage: (sessionId: string, message: Message) => void;
  updateLastMessage: (sessionId: string, content: string) => void;
  setStreaming: (streaming: boolean) => void;
  setModel: (modelId: string) => void;
  updateSessionTitle: (id: string, title: string) => void;
  toggleRag: (sessionId: string) => void;
  clearSession: (sessionId: string) => void;
  setError: (error: string | null) => void;
  stopStreaming: () => void;
  isAborted: () => boolean;

  // 异步操作
  sendMessage: (sessionId: string, content: string) => Promise<void>;
  loadModels: () => Promise<void>;
}

export const useChatStore = create<ChatStore>()(
  subscribeWithSelector((set, get) => ({
    sessions: [],
    currentSessionId: null,
    models: [],
    selectedModel: "",
    isStreaming: false,
    isLoading: false,
    error: null,
    abortController: null,
    isInitialized: false,

    setCurrentSession: (id) => set({ currentSessionId: id }),

    addSession: () => {
      const state = get();
      const newSession: ChatSession = {
        id: Date.now().toString(),
        title: "新对话",
        model: state.selectedModel || "",
        messages: [],
        createdAt: new Date(),
        updatedAt: new Date(),
        useRag: false,
      };
      set((state) => ({
        sessions: [newSession, ...state.sessions],
        currentSessionId: newSession.id,
      }));
    },

    deleteSession: (id) =>
      set((state) => {
        const newSessions = state.sessions.filter((s) => s.id !== id);
        return {
          sessions: newSessions,
          currentSessionId:
            state.currentSessionId === id
              ? newSessions[0]?.id || null
              : state.currentSessionId,
        };
      }),

    addMessage: (sessionId, message) =>
      set((state) => ({
        sessions: state.sessions.map((s) =>
          s.id === sessionId
            ? {
                ...s,
                messages: [...s.messages, message],
                updatedAt: new Date(),
                title:
                  s.messages.length === 0 && message.role === "user"
                    ? message.content.slice(0, 30) + (message.content.length > 30 ? "..." : "")
                    : s.title,
              }
            : s
        ),
      })),

    updateLastMessage: (sessionId, content) =>
      set((state) => ({
        sessions: state.sessions.map((s) =>
          s.id === sessionId
            ? {
                ...s,
                messages: s.messages.map((m, i) =>
                  i === s.messages.length - 1 ? { ...m, content } : m
                ),
                updatedAt: new Date(),
              }
            : s
        ),
      })),

    setStreaming: (streaming) => set({ isStreaming: streaming }),

    setModel: (modelId) => set({ selectedModel: modelId }),

    updateSessionTitle: (id, title) =>
      set((state) => ({
        sessions: state.sessions.map((s) =>
          s.id === id ? { ...s, title, updatedAt: new Date() } : s
        ),
      })),

    toggleRag: (sessionId) =>
      set((state) => ({
        sessions: state.sessions.map((s) =>
          s.id === sessionId ? { ...s, useRag: !s.useRag } : s
        ),
      })),

    clearSession: (sessionId) =>
      set((state) => ({
        sessions: state.sessions.map((s) =>
          s.id === sessionId
            ? {
                ...s,
                messages: [],
                title: "新对话",
                updatedAt: new Date(),
              }
            : s
        ),
      })),

    setError: (error) => set({ error }),

    stopStreaming: () => {
      const { abortController } = get();
      if (abortController) {
        abortController.abort();
        set({ abortController: null, isStreaming: false });
      }
    },

    isAborted: () => {
      const { abortController } = get();
      return abortController ? abortController.signal.aborted : false;
    },

    /**
     * 发送消息并获取 AI 响应
     */
    sendMessage: async (sessionId, content) => {
      const state = get();
      const session = state.sessions.find((s) => s.id === sessionId);
      if (!session) return;

      // 如果模型未加载，先加载
      const settingsStore = useSettingsStore.getState();
      if (!settingsStore.models.length) {
        console.log("模型未加载，等待同步...");
        await settingsStore.syncModelsFromBackend();
      }

      // 创建 AbortController 用于取消请求
      const abortController = new AbortController();
      set({ abortController, error: null });

      // 从 settings store 获取所选模型的完整配置
      const settingsModels = useSettingsStore.getState().models;
      console.log("=== 发送消息 ===");
      console.log("selectedModel (store):", state.selectedModel);
      console.log("settingsModels:", settingsModels.map(m => ({ id: m.id, name: m.name })));

      const selectedModelConfig = settingsModels.find(
        (m: ModelConfig) => m.id === state.selectedModel
      );
      console.log("找到的模型配置:", selectedModelConfig);

      // 添加用户消息
      const userMessage: Message = {
        id: Date.now().toString(),
        role: "user",
        content,
        createdAt: new Date(),
      };
      get().addMessage(sessionId, userMessage);

      set({ isStreaming: true });

      try {
        // 构建消息历史 (用于上下文)
        const messages = session.messages.map((m) => ({
          role: m.role,
          content: m.content,
        }));
        messages.push({ role: "user", content });

        // 添加空的 AI 消息占位
        const assistantMessageId = (Date.now() + 1).toString();
        get().addMessage(sessionId, {
          id: assistantMessageId,
          role: "assistant",
          content: "",
          createdAt: new Date(),
          model: state.selectedModel,
        });

        console.log("=== 发送调试信息 ===");
        console.log("selectedModel:", state.selectedModel);
        console.log("settingsModels:", settingsModels.map(m => ({ id: m.id, name: m.name })));
        console.log("selectedModelConfig:", selectedModelConfig);

        // 构造模型配置
        const modelConfig = selectedModelConfig
          ? {
              name: selectedModelConfig.name,
              type: selectedModelConfig.type,
              base_url: selectedModelConfig.baseUrl,
              api_key: selectedModelConfig.apiKey || "",
              model_name: selectedModelConfig.modelName || "",
            }
          : undefined;

        let fullContent = "";

        try {
          // 非流式请求
          const requestData = {
            model_id: state.selectedModel,
            messages,
            stream: false,
            model_config: modelConfig,
          };

          const response = await sendChat(requestData, abortController.signal);
          fullContent = response.content || "";
          get().updateLastMessage(sessionId, fullContent);
        } catch (chatErr) {
          if (abortController.signal.aborted) {
            console.log("请求已被用户取消");
            get().updateLastMessage(sessionId, fullContent + "\n\n[已停止生成]");
            return;
          }
          console.error("请求失败:", chatErr);
          // 备用：尝试流式请求
          try {
            for await (const chunk of streamChat({
              model_id: state.selectedModel,
              messages,
              stream: true,
              model_config: modelConfig,
            }, abortController.signal)) {
              if (abortController.signal.aborted) {
                console.log("流式请求已被用户取消");
                get().updateLastMessage(sessionId, fullContent + "\n\n[已停止生成]");
                return;
              }
              fullContent += chunk;
              get().updateLastMessage(sessionId, fullContent);
            }
          } catch {
            if (abortController.signal.aborted) {
              get().updateLastMessage(sessionId, fullContent + "\n\n[已停止生成]");
              return;
            }
            throw chatErr;
          }
        }
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "发送消息失败";
        set({ error: errorMessage });
        get().updateLastMessage(sessionId, `[错误] ${errorMessage}`);
      } finally {
        set({ isStreaming: false, abortController: null });
      }
    },

    /**
     * 从设置页面加载模型列表
     */
    loadModels: async () => {
      const state = get();

      // 先从后端同步模型配置
      await useSettingsStore.getState().syncModelsFromBackend();

      // 从 settings store 获取 LLM 和多模态类型的模型
      const settingsModels = useSettingsStore.getState().models;
      const llmModels = settingsModels.filter((m: ModelConfig) => m.type === "llm" || m.type === "multimodal");

      console.log("=== 加载模型 ===");
      console.log("从 settingsStore 获取到模型:", llmModels.map(m => ({ id: m.id, name: m.name })));

      if (llmModels.length === 0) {
        console.warn("未找到可用的 LLM 模型，请在设置中添加");
        return;
      }

      // 同步模型到后端
      try {
        await fetch(`${API_BASE}/models/sync`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(llmModels.map((m: ModelConfig) => ({
            name: m.name,
            type: m.type,
            base_url: m.baseUrl,
            api_key: m.apiKey || "",
            model_name: m.modelName || "",
          }))),
        });
      } catch (e) {
        console.error("同步模型到后端失败:", e);
      }

      // 构建模型选项，使用后端返回的 id
      const modelOptions: ModelOption[] = llmModels.map((m: ModelConfig) => ({
        id: m.id,
        name: m.name,
        provider: m.modelName || "",
        isFavorite: true,
      }));

      // 保留已选中的模型（如果存在），否则选择第一个
      const validSelected = state.selectedModel &&
        modelOptions.some(m => m.id === state.selectedModel);
      const newSelectedModel = validSelected
        ? state.selectedModel
        : modelOptions[0]?.id || "";

      console.log("模型选项:", modelOptions);
      console.log("选中的模型:", newSelectedModel);

      set({
        models: modelOptions,
        selectedModel: newSelectedModel,
        isInitialized: true,
      });
    },
  }))
);

// 监听 settingsStore.models 的变化，自动更新 chatStore
useSettingsStore.subscribe(
  (state) => state.models,
  (models: ModelConfig[]) => {
    const chatStore = useChatStore.getState();
    if (chatStore.isInitialized && models.length > 0) {
      // 从 settingsStore 的模型列表中找出对应的模型，更新 chatStore
      const llmModels = models.filter((m) => m.type === "llm");
      const modelOptions: ModelOption[] = llmModels.map((m) => ({
        id: m.id,
        name: m.name,
        provider: m.modelName || "",
        isFavorite: true,
      }));

      const validSelected = chatStore.selectedModel &&
        modelOptions.some(m => m.id === chatStore.selectedModel);
      const newSelectedModel = validSelected
        ? chatStore.selectedModel
        : modelOptions[0]?.id || "";

      console.log("=== 模型从 settingsStore 更新 ===");
      console.log("模型列表:", modelOptions);
      console.log("选中:", newSelectedModel);

      useChatStore.setState({
        models: modelOptions,
        selectedModel: newSelectedModel,
      });
    }
  }
);