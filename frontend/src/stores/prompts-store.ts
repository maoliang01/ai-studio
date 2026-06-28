import { create } from "zustand";
import type { PromptTemplate, PromptCategory } from "@/types";

const mockCategories: PromptCategory[] = [
  { id: "coding", name: "编程", count: 6 },
  { id: "writing", name: "写作", count: 5 },
  { id: "customer", name: "客服", count: 8 },
  { id: "system", name: "系统", count: 5 },
];

const mockPrompts: PromptTemplate[] = [
  {
    id: "1",
    title: "代码审查助手",
    content: `你是一位资深代码审查专家，精通以下语言和最佳实践：

## 审查范围
- 代码质量与可读性
- 潜在 bug 和安全隐患
- 性能优化建议

## 输出格式
请按以下格式输出审查结果：
1. 总体评价
2. 发现的问题 ({{issue_count}} 个)
3. 改进建议

使用的语言: {{language}}
待审查代码: {{code}}`,
    category: "coding",
    variables: [
      { name: "language", defaultValue: "Python/JavaScript", description: "编程语言" },
      { name: "issue_count", defaultValue: "0", description: "问题数量" },
      { name: "code", defaultValue: "", description: "待审查代码" },
    ],
    usageCount: 42,
    isFavorite: true,
    isPublic: false,
    createdAt: new Date(Date.now() - 86400000 * 5),
    updatedAt: new Date(Date.now() - 86400000),
  },
  {
    id: "2",
    title: "技术文档生成器",
    content: `作为技术文档专家，请为以下内容生成专业的技术文档：

## 基本信息
- 项目名称: {{project_name}}
- 技术栈: {{tech_stack}}
- 目标读者: {{target_audience}}

## 要求
1. 结构清晰，层次分明
2. 包含使用示例
3. 标注注意事项`,
    category: "coding",
    variables: [
      { name: "project_name", defaultValue: "", description: "项目名称" },
      { name: "tech_stack", defaultValue: "", description: "技术栈" },
      { name: "target_audience", defaultValue: "开发者", description: "目标读者" },
    ],
    usageCount: 28,
    isFavorite: false,
    isPublic: true,
    createdAt: new Date(Date.now() - 86400000 * 10),
    updatedAt: new Date(Date.now() - 86400000 * 3),
  },
  {
    id: "3",
    title: "客服回复模板",
    content: `你是一位专业的客服代表，请根据用户问题给出友好的回复。

## 用户问题
{{user_question}}

## 要求
- 语言友好、专业
- 给出具体解决方案
- 如需转人工，明确说明`,
    category: "customer",
    variables: [
      { name: "user_question", defaultValue: "", description: "用户问题" },
    ],
    usageCount: 156,
    isFavorite: true,
    isPublic: false,
    createdAt: new Date(Date.now() - 86400000 * 15),
    updatedAt: new Date(Date.now() - 86400000 * 5),
  },
];

interface PromptsStore {
  prompts: PromptTemplate[];
  categories: PromptCategory[];
  selectedCategoryId: string | null;
  selectedPromptId: string | null;
  searchQuery: string;

  // Actions
  selectCategory: (id: string | null) => void;
  selectPrompt: (id: string | null) => void;
  addPrompt: (prompt: PromptTemplate) => void;
  updatePrompt: (id: string, prompt: Partial<PromptTemplate>) => void;
  deletePrompt: (id: string) => void;
  toggleFavorite: (id: string) => void;
  setSearchQuery: (query: string) => void;
}

export const usePromptsStore = create<PromptsStore>((set) => ({
  prompts: mockPrompts,
  categories: mockCategories,
  selectedCategoryId: null,
  selectedPromptId: "1",
  searchQuery: "",

  selectCategory: (id) => set({ selectedCategoryId: id }),
  selectPrompt: (id) => set({ selectedPromptId: id }),

  addPrompt: (prompt) =>
    set((state) => ({ prompts: [prompt, ...state.prompts] })),

  updatePrompt: (id, updates) =>
    set((state) => ({
      prompts: state.prompts.map((p) =>
        p.id === id ? { ...p, ...updates, updatedAt: new Date() } : p
      ),
    })),

  deletePrompt: (id) =>
    set((state) => ({
      prompts: state.prompts.filter((p) => p.id !== id),
      selectedPromptId:
        state.selectedPromptId === id ? null : state.selectedPromptId,
    })),

  toggleFavorite: (id) =>
    set((state) => ({
      prompts: state.prompts.map((p) =>
        p.id === id ? { ...p, isFavorite: !p.isFavorite } : p
      ),
    })),

  setSearchQuery: (query) => set({ searchQuery: query }),
}));