import { create } from "zustand";
import type { ScrapeOptions, ScrapeResult, DeepScrapeResult } from "@/types";

/**
 * 将后端返回的 snake_case 转换为前端 camelCase 格式
 */
function normalizeScrapeResult(raw: Record<string, unknown>): ScrapeResult {
  return {
    url: String(raw.url || ""),
    title: String(raw.title || ""),
    content: String(raw.content || ""),
    html: raw.html ? String(raw.html) : undefined,
    wordCount: Number(raw.word_count ?? raw.wordCount ?? 0),
    links: Array.isArray(raw.links) ? raw.links.map(String) : [],
    status: raw.status === "error" ? "error" : "success",
    errorMessage: raw.error_message as string | undefined,
    scrapedAt: String(raw.scraped_at || raw.scrapedAt || new Date().toISOString()),
    // 新增字段
    publishedAt: raw.published_at as string | undefined,
    author: raw.author as string | undefined,
    summary: raw.summary as string | undefined,
    keywords: Array.isArray(raw.keywords) ? raw.keywords.map(String) : [],
  };
}

interface ScrapeStore {
  // 状态
  results: ScrapeResult[];
  isScraping: boolean;
  currentResult: ScrapeResult | null;
  error: string | null;
  progress: { current: number; total: number } | null;  // 爬取进度

  // Actions
  scrapeUrl: (url: string, options?: Partial<ScrapeOptions>) => Promise<ScrapeResult | null>;
  scrapeBatch: (urls: string[], options?: Partial<ScrapeOptions>) => Promise<ScrapeResult[]>;
  scrapeSources: (sourceIds?: string[], options?: Partial<ScrapeOptions>) => Promise<ScrapeResult[]>;
  deepScrape: (url: string, maxArticles?: number, options?: Partial<ScrapeOptions>) => Promise<ScrapeResult[]>;
  clearResults: () => void;
  setCurrentResult: (result: ScrapeResult | null) => void;
}

const defaultOptions: ScrapeOptions = {
  extractContent: true,
  fetchHtml: false,
  preserveFormat: false,
  maxDepth: 0,
  timeout: 30,
};

export const useScrapeStore = create<ScrapeStore>((set, get) => ({
  results: [],
  isScraping: false,
  currentResult: null,
  error: null,
  progress: null,

  /**
   * 爬取单个 URL
   */
  scrapeUrl: async (url: string, options?: Partial<ScrapeOptions>) => {
    set({ isScraping: true, error: null });

    try {
      const requestData = {
        url,
        options: { ...defaultOptions, ...options },
      };

      const res = await fetch("/api/scrape", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestData),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || "爬取失败");
      }

      const rawResult = await res.json();
      const result = normalizeScrapeResult(rawResult);

      // 更新历史记录
      set((state) => ({
        results: [result, ...state.results],
        currentResult: result,
        isScraping: false,
      }));

      return result;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "未知错误";
      set({ error: errorMessage, isScraping: false });
      return null;
    }
  },

  /**
   * 批量爬取多个 URL
   */
  scrapeBatch: async (urls: string[], options?: Partial<ScrapeOptions>) => {
    set({ isScraping: true, error: null });

    try {
      const requestData = {
        urls,
        options: { ...defaultOptions, ...options },
      };

      const res = await fetch("/api/scrape/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestData),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || "批量爬取失败");
      }

      const rawResults = await res.json();
      const results = rawResults.map((r: Record<string, unknown>) => normalizeScrapeResult(r));

      // 更新历史记录
      set((state) => ({
        results: [...results, ...state.results],
        currentResult: results[0] || null,
        isScraping: false,
      }));

      return results;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "未知错误";
      set({ error: errorMessage, isScraping: false });
      return [];
    }
  },

  /**
   * 从配置的爬取源爬取
   */
  scrapeSources: async (sourceIds?: string[], options?: Partial<ScrapeOptions>) => {
    set({ isScraping: true, error: null });

    try {
      const requestData = {
        source_ids: sourceIds,
        options: { ...defaultOptions, ...options },
      };

      const res = await fetch("/api/scrape/sources", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestData),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || "从爬取源爬取失败");
      }

      const rawResults = await res.json();
      const results = rawResults.map((r: Record<string, unknown>) => normalizeScrapeResult(r));

      // 更新历史记录
      set((state) => ({
        results: [...results, ...state.results],
        currentResult: results[0] || null,
        isScraping: false,
      }));

      return results;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "未知错误";
      set({ error: errorMessage, isScraping: false });
      return [];
    }
  },

  /**
   * 清空历史记录
   */
  clearResults: () => {
    set({ results: [], currentResult: null, progress: null });
  },

  /**
   * 深度爬取：从列表页自动识别并爬取文章
   */
  deepScrape: async (
    url: string,
    maxArticles: number = 10,
    options?: Partial<ScrapeOptions>
  ) => {
    set({ isScraping: true, error: null, progress: { current: 0, total: 1 } });

    try {
      const requestData = {
        url,
        options: { ...defaultOptions, ...options },
        max_articles: maxArticles,
      };

      const res = await fetch("/api/scrape/deep", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestData),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || "深度爬取失败");
      }

      const data = await res.json();

      // 转换列表页结果
      const listPage = normalizeScrapeResult(data.list_page);

      // 转换文章结果
      const articles: ScrapeResult[] = data.articles.map((r: Record<string, unknown>) =>
        normalizeScrapeResult(r)
      );

      // 更新历史记录：列表页 + 所有文章
      set((state) => ({
        results: [listPage, ...articles, ...state.results],
        currentResult: listPage,
        isScraping: false,
        progress: { current: articles.length, total: articles.length },
      }));

      return articles;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "未知错误";
      set({ error: errorMessage, isScraping: false, progress: null });
      return [];
    }
  },

  /**
   * 设置当前结果
   */
  setCurrentResult: (result: ScrapeResult | null) => {
    set({ currentResult: result });
  },
}));