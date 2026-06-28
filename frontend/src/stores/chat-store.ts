import { create } from "zustand";
import type { ChatSession, Message, ModelConfig } from "@/types";
import { sendChat, streamChat } from "@/lib/api";
import { useSettingsStore } from "./settings-store";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

  // 异步操作
  sendMessage: (sessionId: string, content: string) => Promise<void>;
  loadModels: () => Promise<void>;
}

export const useChatStore = create<ChatStore>((set, get) => ({
  sessions: [],
  currentSessionId: null,
  models: [],
  selectedModel: "",
  isStreaming: false,
  isLoading: false,
  error: null,

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

  /**
   * 发送消息并获取 AI 响应
   */
  sendMessage: async (sessionId, content) => {
    const state = get();
    const session = state.sessions.find((s) => s.id === sessionId);
    if (!session) return;

    // 从 settings store 获取所选模型的完整配置
    const settingsModels = useSettingsStore.getState().models;
    const selectedModelConfig = settingsModels.find(
      (m: ModelConfig) => m.id === state.selectedModel
    );

    // 添加用户消息
    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content,
      createdAt: new Date(),
    };
    get().addMessage(sessionId, userMessage);

    set({ isStreaming: true, error: null });

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

      // 打印调试信息
      console.log("=== 发送调试信息 ===");
      console.log("selectedModel:", state.selectedModel);
      console.log("settingsModels:", settingsModels.map(m => ({ id: m.id, name: m.name, apiKey: m.apiKey ? '***' : 'empty' })));
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

      console.log("modelConfig:", modelConfig);

      // 先尝试非流式请求（更稳定）
      let fullContent = "";

      try {
        const requestData = {
          model_id: state.selectedModel,
          messages,
          stream: false,
          model_config: modelConfig,
        };
        console.log("实际发送的请求数据:", JSON.stringify(requestData));

        const response = await sendChat(requestData);
        console.log("收到响应:", response);
        fullContent = response.content || "";
        get().updateLastMessage(sessionId, fullContent);
      } catch (chatErr) {
        console.error("请求失败:", chatErr);
        // 备用：尝试流式请求
        try {
          for await (const chunk of streamChat({
            model_id: state.selectedModel,
            messages,
            stream: true,
            model_config: modelConfig,
          })) {
            fullContent += chunk;
            get().updateLastMessage(sessionId, fullContent);
          }
        } catch {
          // 流式也失败
          throw chatErr;
        }
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "发送消息失败";
      set({ error: errorMessage });

      // 更新最后一条消息为错误信息
      get().updateLastMessage(sessionId, `[错误] ${errorMessage}`);
    } finally {
      set({ isStreaming: false });
    }
  },

  /**
   * 从设置页面加载模型列表（直接从前端 store 获取）
   */
  loadModels: async () => {
    const state = get();

    // 从 settings store 获取 LLM 类型的模型
    const settingsModels = useSettingsStore.getState().models;
    const llmModels = settingsModels.filter((m: ModelConfig) => m.type === "llm");

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

    const modelOptions: ModelOption[] = llmModels.map((m: ModelConfig) => ({
      id: m.id,
      name: m.name,
      provider: m.modelName || "",
      isFavorite: true,
    }));

    // 自动选择第一个模型（如果没有选中的模型）
    const newSelectedModel = state.selectedModel || modelOptions[0]?.id || "";

    set({
      models: modelOptions,
      selectedModel: newSelectedModel,
    });
  },
}));