# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 提供代码协作指导。

## 基本规则

- **永远使用中文与用户对话**
- 仅在代码本身或用户明确要求时使用英文

---

## 项目概述

AI Studio 是一个 AI 工作台，包含以下核心功能：

1. **多模型对话** - 支持多种大模型 API 的流式对话
2. **知识库 (RAG)** - 文档管理、向量检索增强生成
3. **提示词管理** - 模板创建、分类管理
4. **网页爬取** - 抓取网页内容并导入知识库

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Next.js 14 + React + TypeScript + TailwindCSS + shadcn/ui |
| 状态管理 | Zustand |
| 后端 | FastAPI (Python) + uvicorn |
| HTTP 客户端 | httpx (后端) |
| 爬取引擎 | crawl4ai |
| 包管理 | npm (前端) + pip (后端) |

---

## 项目结构

```
AI Studio/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/               # API 路由
│   │   │   ├── chat.py        # 对话 API
│   │   │   ├── models.py      # 模型配置 API
│   │   │   ├── scrape.py      # 爬取 API
│   │   │   └── settings.py    # 设置 API
│   │   ├── core/              # 核心服务
│   │   │   ├── config.py      # 配置管理
│   │   │   └── llm.py         # LLM 服务层
│   │   ├── schemas/           # Pydantic models
│   │   └── services/          # 业务服务
│   │       └── scraper.py     # 爬虫服务
│   ├── scripts/               # 辅助脚本
│   ├── models_config.json     # 模型配置文件
│   └── requirements.txt       # Python 依赖
│
├── frontend/                   # Next.js 前端
│   ├── src/
│   │   ├── app/               # 页面路由
│   │   │   ├── api/           # API 代理路由
│   │   │   ├── knowledge/     # 知识库页面
│   │   │   ├── prompts/       # 提示词管理页面
│   │   │   ├── scrape/        # 爬取页面
│   │   │   └── settings/      # 设置页面
│   │   ├── components/        # UI 组件
│   │   │   ├── ui/            # shadcn/ui 组件库
│   │   │   └── layout/        # 布局组件
│   │   ├── stores/            # Zustand 状态管理
│   │   ├── lib/               # 工具函数
│   │   │   ├── api.ts         # API 客户端
│   │   │   └── utils.ts       # 通用工具
│   │   └── types/             # TypeScript 类型定义
│   └── package.json
│
└── docs/                      # 文档
```

---

## 常用命令

### 前端开发
```bash
cd frontend
npm run dev          # 启动开发服务器 (http://localhost:3000)
npm run build        # 生产构建
npm run lint         # 代码检查
```

### 后端开发
```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000  # 启动后端 (http://localhost:8000)
```

---

## API 架构

前端通过 Next.js API Routes 作为 BFF (Backend for Frontend) 代理到后端：

```
前端 → /api/* → 后端 /api/* (8080)
```

**主要后端端点：**
- `POST /api/chat` - 发送消息
- `POST /api/chat/stream` - 流式对话 (SSE)
- `GET /api/models` - 获取模型列表
- `POST /api/scrape` - 爬取网页
- `GET/PUT /api/settings` - 获取/保存设置

---

## 代码风格

- **TypeScript**: 使用 camelCase 命名类型/变量
- **前端内部类型**: camelCase
- **后端 Schema**: snake_case (与 Python 惯例保持一致)
- 前端 API 代理自动处理命名转换
- 单个文件不超过 500 行，函数保持单一职责
- 简洁优先，不添加未请求的功能

---

## 安全注意事项

- `backend/models_config.json` 包含敏感信息，勿提交到版本控制
- API Key 通过环境变量或配置文件管理
- 使用 .gitignore 排除敏感文件

---

## 下一步

- 完善单元测试
- 添加 Docker 支持
- 集成向量数据库 (如 Pinecone/Milvus) 用于 RAG