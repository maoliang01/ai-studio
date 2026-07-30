# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 提供代码协作指导。

## 基本规则

- **永远使用中文与用户对话**
- 仅在代码本身或用户明确要求时使用英文

---

## 代码处理规则

### 改动最小化原则
- **只改必要代码** - 严格限制修改范围，仅修改与任务直接相关的代码
- **禁止无关重构** - 不得借机重构、优化或"顺手改进"功能无关的代码
- **保持原有风格** - 即使现有代码风格不理想，也保持一致，不做风格统一
- **最小侵入** - 优先使用配置、环境变量等方式解决问题，避免修改核心逻辑

### 验收节点机制
- **修改完成后自验** - 代码改动后必须进行功能验证（启动服务、调用接口、页面测试）
- **验证通过才通知** - 只有确认改动生效且无副作用后，才向用户报告完成
- **失败主动报告** - 验证失败时立即告知用户具体错误和原因，不隐瞒问题
- **验收清单** - 每次任务列出验收项，逐项确认后再结束

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

## 部署检查清单

**⚠️ 新设备部署时必须确认：**

1. **后端端口配置一致**
   - 后端默认启动端口: `8080`
   - 前端 API 代理配置: `frontend/.env.local` 中的 `BACKEND_URL`
   - 确保两者端口一致，否则所有 API 请求会返回 500 错误

2. **环境变量配置**
   ```bash
   # 创建 frontend/.env.local
   echo "BACKEND_URL=http://localhost:8080" > frontend/.env.local
   ```

3. **数据库配置**
   - PostgreSQL 连接信息: `backend/.env`
   - 默认数据库: `ai_studio`，用户: `postgres`，密码: `postgres`

4. **验证配置**
   ```bash
   # 检查前端 API 代理是否指向正确的后端
   grep -r "localhost:8[0-9][0-9][0-9]" frontend/src/app/api/
   ```

---

## 下一步

- 完善单元测试
- 添加 Docker 支持
- 集成向量数据库 (如 Pinecone/Milvus) 用于 RAG