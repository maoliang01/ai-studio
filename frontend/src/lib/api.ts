/**
 * API 客户端封装
 * 统一处理与后端的 API 通信
 */
import type {
  ChatRequestAPI,
  ChatResponseAPI,
  ModelInfo,
  ModelConfigInput,
  TestResult,
  ScrapeOptions,
  ScrapeResult,
} from "@/types";

const API_BASE = "/api";

// ================================================
// 对话 API
// ================================================

/**
 * 发送对话请求
 */
export async function sendChat(request: ChatRequestAPI, signal?: AbortSignal): Promise<ChatResponseAPI> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });

  if (!response.ok) {
    throw new Error(`聊天请求失败: ${response.status}`);
  }

  return response.json();
}

/**
 * 发送流式对话请求 (SSE)
 */
export async function* streamChat(
  request: ChatRequestAPI,
  signal?: AbortSignal
): AsyncGenerator<string, void, unknown> {
  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });

  if (!response.ok) {
    throw new Error(`聊天请求失败: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("无法读取响应流");
  }

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (signal?.aborted) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6);
          try {
            const parsed = JSON.parse(data);
            if (parsed.content || parsed.done) {
              yield parsed.content;
            }
            if (parsed.done) return;
          } catch {
            // 忽略解析错误
          }
        }
      }
    }
  } finally {
    reader.cancel().catch(() => {});
  }
}

/**
 * 获取后端可用模型列表
 */
export async function fetchAvailableModels(): Promise<{ id: string; name: string; model_name?: string }[]> {
  const response = await fetch(`${API_BASE}/chat/models`);
  if (!response.ok) {
    throw new Error(`获取可用模型失败: ${response.status}`);
  }
  return response.json();
}

// ================================================
// 模型管理 API
// ================================================

/**
 * 获取已配置的模型列表
 */
export async function fetchModels(): Promise<ModelInfo[]> {
  const response = await fetch(`${API_BASE}/models`);
  if (!response.ok) {
    throw new Error(`获取模型列表失败: ${response.status}`);
  }
  return response.json();
}

/**
 * 添加模型
 */
export async function createModel(config: ModelConfigInput): Promise<ModelInfo> {
  const response = await fetch(`${API_BASE}/models`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });

  if (!response.ok) {
    throw new Error(`添加模型失败: ${response.status}`);
  }

  return response.json();
}

/**
 * 更新模型配置
 */
export async function updateModel(modelId: string, config: ModelConfigInput): Promise<ModelInfo> {
  const response = await fetch(`${API_BASE}/models/${modelId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });

  if (!response.ok) {
    throw new Error(`更新模型失败: ${response.status}`);
  }

  return response.json();
}

/**
 * 删除模型
 */
export async function deleteModel(modelId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/models/${modelId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(`删除模型失败: ${response.status}`);
  }
}

/**
 * 测试模型连接
 */
export async function testModel(modelId: string): Promise<TestResult> {
  const response = await fetch(`${API_BASE}/models/${modelId}/test`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(`测试模型连接失败: ${response.status}`);
  }

  return response.json();
}

/**
 * 同步模型配置到后端
 */
export async function syncModels(models: ModelConfigInput[]): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE}/models/sync`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(models),
  });

  if (!response.ok) {
    throw new Error(`同步模型失败: ${response.status}`);
  }

  return response.json();
}

// ================================================
// 爬取 API
// ================================================

/**
 * 爬取单个 URL
 */
export async function scrapeUrl(url: string, options?: Partial<ScrapeOptions>): Promise<ScrapeResult> {
  const response = await fetch(`${API_BASE}/scrape`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, options }),
  });

  if (!response.ok) {
    throw new Error(`爬取失败: ${response.status}`);
  }

  return response.json();
}

/**
 * 批量爬取多个 URL
 */
export async function scrapeBatch(urls: string[], options?: Partial<ScrapeOptions>): Promise<ScrapeResult[]> {
  const response = await fetch(`${API_BASE}/scrape/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ urls, options }),
  });

  if (!response.ok) {
    throw new Error(`批量爬取失败: ${response.status}`);
  }

  return response.json();
}

// ================================================
// 设置 API
// ================================================

/**
 * 获取设置
 */
export async function fetchSettings(): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE}/settings`);
  if (!response.ok) {
    throw new Error(`获取设置失败: ${response.status}`);
  }
  return response.json();
}

/**
 * 保存设置
 */
export async function saveSettings(data: Record<string, unknown>): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE}/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error(`保存设置失败: ${response.status}`);
  }

  return response.json();
}