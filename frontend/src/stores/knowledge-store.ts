import { create } from "zustand";
import type { Document } from "@/types";

// 将 Article 映射为 Document 的接口
interface ArticleAsDocument {
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
  // 文章特有字段
  url?: string;
  content?: string;
  wordCount?: number;
  categoryName?: string;
  categoryId?: string;
  sourceName?: string;
  sourceId?: string;
  publishedAt?: string;
  scrapedAt?: string;  // 爬取时间
  scrapedAtDisplay?: string;  // 格式化显示的爬取时间
}

interface KnowledgeStore {
  documents: ArticleAsDocument[];
  selectedDocumentId: string | null;
  searchQuery: string;
  isUploading: boolean;
  isLoading: boolean;

  // Actions
  selectDocument: (id: string | null) => void;
  addDocument: (doc: ArticleAsDocument) => void;
  deleteDocument: (id: string) => void;
  updateDocumentStatus: (id: string, status: "pending" | "indexing" | "indexed" | "error") => void;
  setSearchQuery: (query: string) => void;
  setUploading: (uploading: boolean) => void;
  loadDocuments: () => Promise<void>;
}

// 将后端文章数据转换为前端文档格式
function articleToDocument(article: any): ArticleAsDocument {
  // 估算分块数量：每 500 字一个块
  const wordCount = article.word_count || 0;
  const chunkCount = Math.max(1, Math.ceil(wordCount / 500));

  // 处理爬取时间
  const scrapedAt = article.scraped_at || article.created_at;
  const scrapedAtDate = scrapedAt ? new Date(scrapedAt) : new Date();

  return {
    id: article.id,
    title: article.title || "无标题",
    sourceType: "url",  // 爬取的文章都是 URL 来源
    sourceUrl: article.url,
    fileSize: wordCount * 2,  // 估算文件大小（2字节/字符）
    chunkCount: chunkCount,
    status: "indexed",  // 已在数据库中的文章视为已索引
    tags: article.keywords || [],
    createdAt: scrapedAtDate,
    updatedAt: scrapedAtDate,
    // 文章特有字段
    url: article.url,
    content: article.content,
    wordCount: wordCount,
    categoryName: article.category_name,
    categoryId: article.category_id,
    sourceName: article.source_name,
    sourceId: article.source_id,
    publishedAt: article.published_at,
    scrapedAt: scrapedAt ? scrapedAtDate.toISOString() : undefined,
    scrapedAtDisplay: formatScrapedTime(scrapedAtDate),
  };
}

// 格式化爬取时间显示
function formatScrapedTime(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffMins < 1) return "刚刚";
  if (diffMins < 60) return `${diffMins} 分钟前`;
  if (diffHours < 24) return `${diffHours} 小时前`;
  if (diffDays < 7) return `${diffDays} 天前`;

  // 超过一周显示日期
  return date.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
}

export const useKnowledgeStore = create<KnowledgeStore>((set, get) => ({
  documents: [],
  selectedDocumentId: null,
  searchQuery: "",
  isUploading: false,
  isLoading: false,

  selectDocument: (id) => set({ selectedDocumentId: id }),

  addDocument: (doc) =>
    set((state) => ({
      documents: [doc, ...state.documents],
    })),

  deleteDocument: (id) =>
    set((state) => ({
      documents: state.documents.filter((d) => d.id !== id),
      selectedDocumentId:
        state.selectedDocumentId === id ? null : state.selectedDocumentId,
    })),

  updateDocumentStatus: (id, status) =>
    set((state) => ({
      documents: state.documents.map((d) =>
        d.id === id ? { ...d, status, updatedAt: new Date() } : d
      ),
    })),

  setSearchQuery: (query) => set({ searchQuery: query }),

  setUploading: (uploading) => set({ isUploading: uploading }),

  loadDocuments: async () => {
    set({ isLoading: true });
    try {
      // 从后端 API 获取文章数据作为文档
      const res = await fetch("/api/articles?page_size=100");
      const data = await res.json();

      if (data.items && Array.isArray(data.items)) {
        const documents = data.items.map(articleToDocument);
        set({ documents });

        // 如果有文档且没有选中任何文档，自动选中第一个
        if (documents.length > 0 && !get().selectedDocumentId) {
          set({ selectedDocumentId: documents[0].id });
        }
      }
    } catch (error) {
      console.error("加载文档失败:", error);
    } finally {
      set({ isLoading: false });
    }
  },
}));