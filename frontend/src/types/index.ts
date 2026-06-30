/**
 * AI Studio - 前端类型定义
 * 内部使用 camelCase，与后端 API 交互时自动转换
 */

// ================================================
// 对话相关类型
// ================================================

/** 对话消息 */
export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt: Date;
  model?: string;
  attachments?: Attachment[];
  references?: Reference[];
}

/** 附件 */
export interface Attachment {
  id: string;
  name: string;
  type: string;
  size: number;
  url: string;
}

/** 引用（知识库引用） */
export interface Reference {
  documentId: string;
  chunkId: string;
  content: string;
  score: number;
}

/** 对话会话 */
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

// ================================================
// 知识库相关类型
// ================================================

/** 文档 */
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

/** 文档分块 */
export interface DocumentChunk {
  id: string;
  documentId: string;
  content: string;
  chunkIndex: number;
  createdAt: Date;
}

// ================================================
// 提示词相关类型
// ================================================

/** 提示词模板 */
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

/** 提示词变量 */
export interface PromptVariable {
  name: string;
  defaultValue: string;
  description: string;
}

/** 提示词分类 */
export interface PromptCategory {
  id: string;
  name: string;
  count: number;
}

// ================================================
// 爬取相关类型
// ================================================

/** 爬取选项 */
export interface ScrapeOptions {
  extractContent: boolean;
  fetchHtml: boolean;
  preserveFormat: boolean;
  maxDepth: number;
  timeout: number;
}

/** 爬取结果 */
export interface ScrapeResult {
  url: string;
  title: string;
  content: string;
  html?: string;
  wordCount: number;
  links: string[];
  status: "success" | "error";
  errorMessage?: string;
  scrapedAt: string;
  // 新增：文章元信息
  publishedAt?: string;  // 发布时间
  author?: string;       // 作者
  summary?: string;      // 内容摘要
  keywords?: string[];   // 关键字标签
}

/** 深度爬取响应 */
export interface DeepScrapeResult {
  listPage: ScrapeResult;     // 列表页结果
  articles: ScrapeResult[];   // 文章结果列表
  totalArticles: number;      // 总共爬取的文章数
}

/** 日期范围预设选项 */
export type DateRangePreset = "today" | "week" | "month";

/** 自定义日期范围 */
export interface CustomDateRange {
  startDate?: string;  // YYYY-MM-DD
  endDate?: string;    // YYYY-MM-DD
}

/** 日期范围值 */
export interface DateRangeValue {
  preset?: DateRangePreset;
  custom?: CustomDateRange;
}

/** 爬取级别（页面结构分析） */
export type ScrapeLevel = "list" | "detail" | "deep";

/**
 * 爬取级别说明：
 * - list: 仅爬取列表页（提取所有子链接）
 * - detail: 爬取列表页 + 直接子页面（一级文章）
 * - deep: 深度爬取（递归发现多级文章）
 */

/** 深度爬取请求参数 */
export interface DeepScrapeParams {
  url: string;
  maxArticles?: number;
  dateRange?: DateRangePreset;
  customDateRange?: CustomDateRange;
  scrapeLevel?: ScrapeLevel;
  options?: ScrapeOptions;
}

/** 网页种类 */
export type WebsiteCategory = "government" | "business" | "academic";

/** 爬取源配置 */
export interface ScrapeSource {
  id: string;
  name: string;
  url: string;
  category: WebsiteCategory;
  description?: string;
  isEnabled: boolean;
  createdAt: string;
  updatedAt: string;
}

// ================================================
// 页签识别相关类型
// ================================================

/** 页签节点类型 */
export interface TabNode {
  /** 节点唯一ID */
  id: string;
  /** 节点显示名称 */
  label: string;
  /** 点击后跳转的URL（完整URL或相对路径） */
  url: string;
  /** 子节点列表 */
  children?: TabNode[];
  /** 节点层级（0=顶级导航，1=一级栏目，2=二级栏目...） */
  level: number;
  /** 节点类型：nav=导航菜单, tab=内容区Tab, breadcrumb=面包屑 */
  type: "nav" | "tab" | "breadcrumb";
  /** 是否可展开（Has children） */
  expandable?: boolean;
  /** URL模式说明（如 /category/{id}/） */
  urlPattern?: string;
}

/** 页签树结构 */
export interface TabTree {
  /** 所属网站域名 */
  domain: string;
  /** 网站标题 */
  siteTitle: string;
  /** 根节点 */
  root: TabNode;
  /** 所有节点列表（扁平化，方便遍历） */
  allNodes: TabNode[];
  /** 生成时间 */
  generatedAt: string;
  /** 节点总数 */
  totalCount: number;
}

/** 页签识别请求参数 */
export interface TabAnalyzeParams {
  /** 要分析的URL */
  url: string;
  /** 是否识别导航栏 */
  includeNav?: boolean;
  /** 是否识别内容区Tab */
  includeTabs?: boolean;
  /** 最大递归深度 */
  maxDepth?: number;
}

/** 页签识别结果 */
export interface TabAnalyzeResult {
  /** 是否成功 */
  success: boolean;
  /** 页签树结构 */
  tree?: TabTree;
  /** 错误信息 */
  error?: string;
  /** 耗时（毫秒） */
  duration?: number;
}

// ================================================
// 模型相关类型
// =============================================

/** 模型类型 */
export type ModelType = "llm" | "embedding" | "multimodal";

/** 模型配置（用于添加/更新） */
export interface ModelConfigInput {
  name: string;
  type: ModelType;
  baseUrl: string;
  apiKey?: string;
  modelName?: string;
}

/** 模型信息（用于显示） */
export interface ModelInfo {
  id: string;
  name: string;
  type: ModelType;
  baseUrl: string;
  apiKey?: string;
  modelName?: string;
  isConnected?: boolean;
  latency?: number;
  lastTestedAt?: string;
}

/** 模型测试结果 */
export interface TestResult {
  success: boolean;
  latency?: number;
  error?: string;
  model?: string;
}

// ================================================
// API 请求/响应类型（与后端交互，使用 snake_case 与后端一致）
// ================================================

/** 模型配置（API 请求格式，snake_case） */
export interface ModelConfigAPI {
  name: string;
  type: string;
  base_url: string;
  api_key?: string;
  model_name?: string;
}

/** 聊天消息（API格式） */
export interface ChatMessageAPI {
  role: string;
  content: string;
}

/** 聊天请求 */
export interface ChatRequestAPI {
  model_id?: string;
  messages: ChatMessageAPI[];
  stream?: boolean;
  temperature?: number;
  max_tokens?: number;
  model_config?: ModelConfigAPI;
}

/** 聊天响应 */
export interface ChatResponseAPI {
  content: string;
  model?: string;
  usage?: Record<string, unknown>;
}

/** 爬取源请求 */
export interface ScrapeSourceRequest {
  name: string;
  url: string;
  category?: string;
  description?: string;
  is_enabled?: boolean;
}

// ================================================
// 用户设置
// ================================================

/** 用户设置 */
export interface UserSettings {
  theme: "light" | "dark" | "system";
  primaryColor: string;
  scrapeSources: ScrapeSource[];
}