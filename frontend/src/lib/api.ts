const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ChatMessage {
  role: string;
  content: string;
}

interface ChatRequest {
  model_id?: string;
  messages: ChatMessage[];
  stream?: boolean;
  temperature?: number;
  max_tokens?: number;
  model_config?: {
    name: string;
    type: string;
    base_url: string;
    api_key?: string;
    model_name?: string;
  };
}

interface ChatResponse {
  content: string;
  model?: string;
}

interface ModelInfo {
  id: string;
  name: string;
  type: string;
  base_url: string;
  model_name?: string;
  is_connected?: boolean;
  latency?: number;
  last_tested_at?: string;
}

interface TestResult {
  success: boolean;
  latency?: number;
  error?: string;
}

/**
 * 发送对话请求
 */
export async function sendChat(request: ChatRequest): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`聊天请求失败: ${response.status}`);
  }

  return response.json();
}

/**
 * 发送流式对话请求 (SSE)
 */
export async function* streamChat(request: ChatRequest): AsyncGenerator<string, void, unknown> {
  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
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

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("event: message")) {
        // 跳过事件头部
        continue;
      }
      if (line.startsWith("data: ")) {
        const data = line.slice(6);
        try {
          const parsed = JSON.parse(data);
          if (parsed.content || parsed.done) {
            yield parsed.content;
          }
          if (parsed.done) {
            return;
          }
        } catch {
          // 忽略解析错误
        }
      }
    }
  }
}

/**
 * 获取可用模型列表
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
export async function createModel(config: {
  name: string;
  type: string;
  base_url: string;
  api_key?: string;
  model_name?: string;
}): Promise<ModelInfo> {
  const response = await fetch(`${API_BASE}/models`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
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
export async function updateModel(
  modelId: string,
  config: {
    name: string;
    type: string;
    base_url: string;
    api_key?: string;
    model_name?: string;
  }
): Promise<ModelInfo> {
  const response = await fetch(`${API_BASE}/models/${modelId}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
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
 * 获取后端可用模型列表
 */
export async function fetchAvailableModels(): Promise<{ id: string; name: string; model_name?: string }[]> {
  const response = await fetch(`${API_BASE}/chat/models`);
  if (!response.ok) {
    throw new Error(`获取可用模型失败: ${response.status}`);
  }
  return response.json();
}