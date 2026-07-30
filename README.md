# AI Studio

一个功能完整的 AI 工作台，支持多模型对话、知识库管理、提示词模板和网页爬取功能。

## 🚀 核心功能

### 1. 多模型对话
- 支持多种大语言模型 API
- 流式对话 (SSE) 实时响应
- 对话历史管理

### 2. 知识库 (RAG)
- 文档上传与管理
- 向量检索增强生成
- 智能问答系统

### 3. 提示词管理
- 提示词模板创建
- 分类管理与搜索
- 快速调用常用提示词

### 4. 网页爬取
- 智能网页内容抓取
- 爬取结果导入知识库
- 支持多种网页格式

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | Next.js 14 + React + TypeScript + TailwindCSS + shadcn/ui |
| **状态管理** | Zustand |
| **后端** | FastAPI (Python) + uvicorn |
| **HTTP 客户端** | httpx (后端) |
| **爬取引擎** | crawl4ai |
| **包管理** | npm (前端) + pip (后端) |

## 📁 项目结构

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

## 🚀 快速开始

### 前置要求

- Node.js 18+ (前端)
- Python 3.8+ (后端)
- npm 或 yarn (包管理)

### 1. 克隆项目

```bash
git clone <repository-url>
cd ai-studio
```

### 2. 后端设置

```bash
# 进入后端目录
cd backend

# 创建虚拟环境 (推荐)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env  # 编辑 .env 文件配置数据库等

# 启动后端服务
python -m uvicorn app.main:app --reload --port 8080
```

### 3. 前端设置

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 配置环境变量
echo "BACKEND_URL=http://localhost:8080" > .env.local

# 启动开发服务器
npm run dev
```

### 4. 访问应用

- **前端界面**: http://localhost:3000
- **后端 API**: http://localhost:8080
- **API 文档**: http://localhost:8080/docs (FastAPI 自动生成)

## 🔧 API 架构

前端通过 Next.js API Routes 作为 BFF (Backend for Frontend) 代理到后端：

```
前端 → /api/* → 后端 /api/* (8080)
```

### 主要后端端点

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/api/chat` | 发送消息 |
| POST | `/api/chat/stream` | 流式对话 (SSE) |
| GET | `/api/models` | 获取模型列表 |
| POST | `/api/scrape` | 爬取网页 |
| GET | `/api/settings` | 获取设置 |
| PUT | `/api/settings` | 保存设置 |

## 📝 代码风格

- **TypeScript**: 使用 camelCase 命名类型/变量
- **前端内部类型**: camelCase
- **后端 Schema**: snake_case (与 Python 惯例保持一致)
- 前端 API 代理自动处理命名转换
- 单个文件不超过 500 行，函数保持单一职责

## 🔒 安全注意事项

- `backend/models_config.json` 包含敏感信息，勿提交到版本控制
- API Key 通过环境变量或配置文件管理
- 使用 .gitignore 排除敏感文件

## 🚀 部署

### 部署检查清单

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

## 🧪 开发命令

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

## 📚 文档

- [FastAPI 文档](http://localhost:8000/docs) - 后端 API 文档 (自动生成)
- [Next.js 文档](https://nextjs.org/docs) - 前端框架文档
- [shadcn/ui 文档](https://ui.shadcn.com) - UI 组件库文档

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

### 开发流程

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🙏 致谢

- [Next.js](https://nextjs.org/) - React 框架
- [FastAPI](https://fastapi.tiangolo.com/) - Python Web 框架
- [shadcn/ui](https://ui.shadcn.com/) - UI 组件库
- [TailwindCSS](https://tailwindcss.com/) - CSS 框架
- [Zustand](https://github.com/pmndrs/zustand) - 状态管理

---

**AI Studio** - 让 AI 开发更简单 🚀