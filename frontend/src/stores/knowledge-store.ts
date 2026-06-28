import { create } from "zustand";
import type { Document, DocumentChunk } from "@/types";

const mockDocuments: Document[] = [
  {
    id: "1",
    title: "产品使用手册 v2.0",
    sourceType: "upload",
    fileSize: 2400000,
    chunkCount: 42,
    status: "indexed",
    tags: ["产品", "用户指南"],
    createdAt: new Date(Date.now() - 86400000 * 3),
    updatedAt: new Date(Date.now() - 86400000),
  },
  {
    id: "2",
    title: "API 开发文档",
    sourceType: "url",
    sourceUrl: "https://api.example.com/docs",
    fileSize: 156000,
    chunkCount: 28,
    status: "indexed",
    tags: ["技术", "API"],
    createdAt: new Date(Date.now() - 86400000 * 7),
    updatedAt: new Date(Date.now() - 86400000 * 2),
  },
  {
    id: "3",
    title: "公司介绍",
    sourceType: "upload",
    fileSize: 520000,
    chunkCount: 15,
    status: "indexing",
    tags: ["公司"],
    createdAt: new Date(Date.now() - 86400000),
    updatedAt: new Date(Date.now() - 3600000),
  },
];

interface KnowledgeStore {
  documents: Document[];
  selectedDocumentId: string | null;
  searchQuery: string;
  isUploading: boolean;

  // Actions
  selectDocument: (id: string | null) => void;
  addDocument: (doc: Document) => void;
  deleteDocument: (id: string) => void;
  updateDocumentStatus: (id: string, status: Document["status"]) => void;
  setSearchQuery: (query: string) => void;
  setUploading: (uploading: boolean) => void;
}

export const useKnowledgeStore = create<KnowledgeStore>((set) => ({
  documents: mockDocuments,
  selectedDocumentId: "1",
  searchQuery: "",
  isUploading: false,

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
}));