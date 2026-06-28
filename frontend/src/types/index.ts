// 对话相关类型
export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt: Date;
  model?: string;
  attachments?: Attachment[];
  references?: Reference[];
}

export interface Attachment {
  id: string;
  name: string;
  type: string;
  size: number;
  url: string;
}

export interface Reference {
  documentId: string;
  chunkId: string;
  content: string;
  score: number;
}

export interface ChatSession {
  id: string;
  title: string;
  model: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
  folderId?: string;
  useRag: boolean;
  documents?: string[];
}

// 知识库相关类型
export interface Document {
  id: string;
  title: string;
  sourceType: "upload" | "url";
  sourceUrl?: string;
  fileSize: number;
  chunkCount: number;
  status: "pending" | "indexing" | "indexed" | "error";
  tags: string[];
  createdAt: Date;
  updatedAt: Date;
}

export interface DocumentChunk {
  id: string;
  documentId: string;
  content: string;
  chunkIndex: number;
  embedding?: number[];
  createdAt: Date;
}

// 提示词相关类型
export interface PromptTemplate {
  id: string;
  title: string;
  content: string;
  category: string;
  variables: PromptVariable[];
  usageCount: number;
  isFavorite: boolean;
  isPublic: boolean;
  createdAt: Date;
  updatedAt: Date;
}

export interface PromptVariable {
  name: string;
  defaultValue: string;
  description: string;
}

export interface PromptCategory {
  id: string;
  name: string;
  count: number;
}

// 网页爬取相关类型
export interface ScrapedContent {
  id: string;
  url: string;
  title: string;
  content: string;
  wordCount: number;
  chunkCount: number;
  scrapedAt: Date;
  status: "pending" | "success" | "error";
  errorMessage?: string;
}

// 模型相关类型
export type ModelType = "llm" | "embedding" | "multimodal";

export interface AIModel {
  id: string;
  name: string;
  provider: string;
  isFavorite: boolean;
}

// 大模型配置
export interface ModelConfig {
  id: string;
  name: string;
  type: ModelType;
  baseUrl: string;
  apiKey?: string;
  modelName?: string;  // 模型标识，可能与显示名不同
  isConnected?: boolean;
  latency?: number;    // 延迟ms
  lastTestedAt?: Date;
  createdAt: Date;
}

export interface APIKeyConfig {
  provider: string;
  apiKey: string;
  baseUrl?: string;
  isValid?: boolean;
}

// 用户设置
export interface UserSettings {
  theme: "light" | "dark" | "system";
  primaryColor: string;
  sidebarCollapsed: boolean;
}