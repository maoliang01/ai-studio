# 公众号爬取功能实施计划

> **文档版本**: v1.0
> **创建日期**: 2026-07-30
> **最后更新**: 2026-07-30
> **状态**: 待实施

---

## 一、项目概述

### 1.1 功能目标

扩展 AI Studio 的爬取功能，支持微信公众号文章的自动爬取，并与现有文章管理系统统一集成。

### 1.2 核心需求

| 需求 | 说明 |
|------|------|
| 多公众号支持 | 支持同时爬取多个公众号的文章 |
| 定时监控 | 按时间周期自动爬取（参照现有网页爬取配置） |
| 完整内容获取 | 获取文章完整内容（非标题和链接） |
| Cookie 支持 | 支持浏览器插件导出 Cookie |
| 统一管理 | 与现有文章管理统一，通过字段区分信源 |
| 知识图谱集成 | 自动触发实体关系抽取 |

### 1.3 技术选型

| 组件 | 技术方案 | 说明 |
|------|----------|------|
| 爬虫框架 | MediaCrawler | 原生支持微信公众号 |
| 浏览器自动化 | Playwright | MediaCrawler 底层依赖 |
| 后端框架 | FastAPI | 复用现有架构 |
| 定时任务 | APScheduler | 复用现有调度器 |
| 前端框架 | Next.js + shadcn/ui | 复用现有 UI 库 |

---

## 二、技术架构

### 2.1 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (Next.js)                       │
├─────────────────────────────────────────────────────────────┤
│  /settings/wechat      │  /settings/wechat/accounts        │
│  Cookie 管理界面        │  公众号列表管理                     │
├─────────────────────────────────────────────────────────────┤
│  /settings/wechat/tasks │  /articles                       │
│  爬取任务配置            │  统一文章列表（支持信源筛选）       │
└──────────────────────┬──────────────────────────────────────┘
                       │ API 调用
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    后端 API (FastAPI)                       │
├─────────────────────────────────────────────────────────────┤
│  /api/wechat/cookies    │  /api/wechat/accounts             │
│  Cookie CRUD            │  公众号 CRUD                       │
├─────────────────────────────────────────────────────────────┤
│  /api/wechat/tasks      │  /api/wechat/crawl                │
│  定时任务管理            │  触发爬取                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   核心服务层                                 │
├─────────────────────────────────────────────────────────────┤
│  CookieManager        │  WechatCrawler                     │
│  Cookie 管理           │  MediaCrawler 封装                  │
├─────────────────────────────────────────────────────────────┤
│  WechatPipeline       │  KGSync                           │
│  内容处理管道          │  知识图谱同步                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                      数据存储                               │
├─────────────────────────────────────────────────────────────┤
│  SQLite (articles)    │  Neo4j (知识图谱)                   │
│  + source_type 字段   │  实体、关系                         │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 数据流向

```
公众号文章 URL
      │
      ▼
MediaCrawler 爬取
      │
      ▼
原始内容 (title, content, author, ...)
      │
      ▼
LLM 提取 (标签, 摘要)
      │
      ▼
保存文章 (POST /api/articles)
      │
      ├──→ SQLite (articles 表, source_type='wechat')
      │
      └──→ Neo4j (自动触发 KG 抽取)
```

---

## 三、数据库设计

### 3.1 扩展 articles 表

```sql
-- 新增信源类型字段
ALTER TABLE articles ADD COLUMN source_type VARCHAR(50) DEFAULT 'web';

-- 索引
CREATE INDEX idx_articles_source_type ON articles(source_type);
```

### 3.2 新增 wechat_accounts 表

```sql
CREATE TABLE wechat_accounts (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,           -- 公众号名称
    wechat_id VARCHAR(100),               -- 公众号 ID (gh_xxx)
    description TEXT,                     -- 描述
    is_enabled BOOLEAN DEFAULT TRUE,      -- 是否启用
    last_crawled_at TIMESTAMP,            -- 上次爬取时间
    article_count INTEGER DEFAULT 0,      -- 已爬取文章数
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE INDEX idx_wechat_accounts_enabled ON wechat_accounts(is_enabled);
```

### 3.3 新增 wechat_cookies 表

```sql
CREATE TABLE wechat_cookies (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,           -- Cookie 名称
    cookie_data TEXT NOT NULL,            -- Cookie JSON 数据
    is_active BOOLEAN DEFAULT TRUE,       -- 是否激活
    expires_at TIMESTAMP,                 -- 过期时间
    last_used_at TIMESTAMP,               -- 上次使用时间
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_wechat_cookies_active ON wechat_cookies(is_active);
```

### 3.4 新增 wechat_crawl_tasks 表

```sql
CREATE TABLE wechat_crawl_tasks (
    id VARCHAR(50) PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,      -- 关联公众号
    schedule_type VARCHAR(50) NOT NULL,   -- daily/weekly/monthly
    schedule_time VARCHAR(20),            -- 执行时间 (HH:MM)
    max_articles INTEGER DEFAULT 10,      -- 每次最大爬取数
    is_enabled BOOLEAN DEFAULT TRUE,
    last_run_at TIMESTAMP,
    next_run_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES wechat_accounts(id)
);
```

---

## 四、后端 API 设计

### 4.1 Cookie 管理 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/wechat/cookies` | 获取 Cookie 列表 |
| POST | `/api/wechat/cookies` | 添加 Cookie |
| PUT | `/api/wechat/cookies/:id` | 更新 Cookie |
| DELETE | `/api/wechat/cookies/:id` | 删除 Cookie |
| POST | `/api/wechat/cookies/:id/activate` | 激活 Cookie |
| POST | `/api/wechat/cookies/validate` | 验证 Cookie 有效性 |

### 4.2 公众号管理 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/wechat/accounts` | 获取公众号列表 |
| POST | `/api/wechat/accounts` | 添加公众号 |
| PUT | `/api/wechat/accounts/:id` | 更新公众号 |
| DELETE | `/api/wechat/accounts/:id` | 删除公众号 |
| POST | `/api/wechat/accounts/:id/crawl` | 立即爬取该公众号 |

### 4.3 定时任务 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/wechat/tasks` | 获取任务列表 |
| POST | `/api/wechat/tasks` | 创建定时任务 |
| PUT | `/api/wechat/tasks/:id` | 更新任务 |
| DELETE | `/api/wechat/tasks/:id` | 删除任务 |
| POST | `/api/wechat/tasks/:id/run` | 立即执行任务 |
| POST | `/api/wechat/tasks/:id/toggle` | 启用/禁用任务 |

### 4.4 爬取状态 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/wechat/crawl/status` | 获取爬取进度 |
| GET | `/api/wechat/crawl/history` | 爬取历史记录 |

---

## 五、前端界面设计

### 5.1 页面结构

```
/settings
├── /wechat                    # Cookie 管理
├── /wechat/accounts           # 公众号列表
└── /wechat/tasks              # 定时任务配置

/articles                      # 统一文章列表（新增信源筛选）
```

### 5.2 界面设计原则

1. **保持现有 UI 风格**：使用 shadcn/ui 组件库，保持一致的视觉风格
2. **复用现有组件**：表格、表单、对话框等组件与现有页面保持一致
3. **响应式设计**：支持移动端访问

### 5.3 页面原型

#### Cookie 管理页面 (`/settings/wechat`)

```
┌─────────────────────────────────────────────────────────────┐
│  Cookie 管理                                     [添加 Cookie] │
├─────────────────────────────────────────────────────────────┤
│  📌 浏览器插件推荐                                          │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ 推荐使用 EditThisCookie 或 Cookie-Editor 插件导出 Cookie │ │
│  │ [下载 EditThisCookie]  [下载 Cookie-Editor]            │ │
│  └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  Cookie 列表                                                │
│  ┌──────────────┬──────────┬──────────┬──────────┬─────────┐ │
│  │ 名称         │ 状态     │ 过期时间 │ 操作     │         │ │
│  ├──────────────┼──────────┼──────────┼──────────┼─────────┤ │
│  │ 主账号       │ ✅ 激活  │ 3天后   │ [验证] [删除] │         │ │
│  │ 备用账号     │ ⚠️ 闲置  │ 1天后   │ [激活] [删除] │         │ │
│  └──────────────┴──────────┴──────────┴──────────┴─────────┘ │
└─────────────────────────────────────────────────────────────┘
```

#### 公众号管理页面 (`/settings/wechat/accounts`)

```
┌─────────────────────────────────────────────────────────────┐
│  公众号管理                                  [添加公众号]     │
├─────────────────────────────────────────────────────────────┤
│  公众号列表                                                 │
│  ┌──────────────┬──────────┬──────────┬──────────┬─────────┐ │
│  │ 公众号名称   │ ID       │ 文章数   │ 操作     │         │ │
│  ├──────────────┼──────────┼──────────┼──────────┼─────────┤ │
│  │ 科技日报     │ gh_xxx   │ 128     │ [爬取] [编辑] [删除] │ │
│  │ 人民日报     │ gh_yyy   │ 256     │ [爬取] [编辑] [删除] │ │
│  └──────────────┴──────────┴──────────┴──────────┴─────────┘ │
└─────────────────────────────────────────────────────────────┘
```

#### 文章列表页面 (`/articles`)

```
┌─────────────────────────────────────────────────────────────┐
│  文章管理                                                   │
├─────────────────────────────────────────────────────────────┤
│  筛选条件:                                                  │
│  [信源: 全部 ▼] [分类: 全部 ▼] [状态: 全部 ▼] [搜索...]      │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┬──────────┬──────────┬──────────┬─────────┐ │
│  │ 标题         │ 信源     │ 分类     │ 状态     │ 操作   │ │
│  ├──────────────┼──────────┼──────────┼──────────┼─────────┤ │
│  │ 文章标题1    │ 🌐 网页  │ 科技     │ ✅ 完成  │ [查看]  │ │
│  │ 文章标题2    │ 📱 公众号│ 财经     │ ⏳ 处理中│ [查看]  │ │
│  └──────────────┴──────────┴──────────┴──────────┴─────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 六、实施步骤

### 第一阶段：后端基础模块 (预计 2 天)

| 步骤 | 任务 | 输出文件 | 验收标准 |
|------|------|----------|----------|
| 1 | 克隆 MediaCrawler | `backend/vendor/mediacrawler/` | 能够正常 import |
| 2 | 安装 Playwright 依赖 | `backend/requirements.txt` | 浏览器能够启动 |
| 3 | 创建公众号模块目录 | `backend/app/services/wechat/` | 目录结构完整 |
| 4 | 实现 Cookie 管理器 | `backend/app/services/wechat/cookie_manager.py` | 单元测试通过 |
| 5 | 实现爬虫封装 | `backend/app/services/wechat/crawler.py` | 能够爬取文章内容 |
| 6 | 数据库迁移脚本 | `backend/alembic/versions/add_wechat_tables.py` | 表创建成功 |

### 第二阶段：内容处理管道 (预计 1 天)

| 步骤 | 任务 | 复用代码 | 验收标准 |
|------|------|----------|----------|
| 7 | 实现内容处理管道 | `backend/app/services/wechat/pipeline.py` | 完整流程可运行 |
| 8 | 集成 LLM 标签提取 | `scraper._extract_metadata_with_llm()` | 标签、摘要提取成功 |
| 9 | 集成文章保存 API | `POST /api/articles` | 文章保存成功 |
| 10 | 自动触发 KG 抽取 | `kg_sync.on_article_created()` | 实体关系抽取成功 |

### 第三阶段：定时任务 (预计 1 天)

| 步骤 | 任务 | 说明 | 验收标准 |
|------|------|------|----------|
| 11 | 实现公众号定时爬取任务 | APScheduler | 按配置时间执行 |
| 12 | 实现爬取状态跟踪 | 状态机管理 | 前端可查询进度 |

### 第四阶段：前端界面 (预计 2 天)

| 步骤 | 任务 | 页面 | 验收标准 |
|------|------|------|----------|
| 13 | Cookie 管理界面 | `/settings/wechat` | 增删改查功能完整 |
| 14 | 公众号列表管理 | `/settings/wechat/accounts` | 增删改查功能完整 |
| 15 | 爬取任务配置 | `/settings/wechat/tasks` | 定时任务可配置 |
| 16 | 文章列表筛选 | `/articles` | 支持按信源筛选 |

### 第五阶段：测试验收 (预计 1 天)

| 步骤 | 任务 | 验收标准 |
|------|------|----------|
| 17 | 单元测试 | 覆盖核心功能，覆盖率 > 80% |
| 18 | 端到端测试 | 完整流程验证 |
| 19 | 文档更新 | README + 使用指南 |

---

## 七、前后端绑定清单

### 7.1 后端 API → 前端调用映射

| 后端 API | 前端页面 | 前端函数 |
|----------|----------|----------|
| `GET /api/wechat/cookies` | `/settings/wechat` | `fetchWechatCookies()` |
| `POST /api/wechat/cookies` | `/settings/wechat` | `createWechatCookie()` |
| `DELETE /api/wechat/cookies/:id` | `/settings/wechat` | `deleteWechatCookie()` |
| `POST /api/wechat/cookies/:id/activate` | `/settings/wechat` | `activateWechatCookie()` |
| `POST /api/wechat/cookies/validate` | `/settings/wechat` | `validateWechatCookie()` |
| `GET /api/wechat/accounts` | `/settings/wechat/accounts` | `fetchWechatAccounts()` |
| `POST /api/wechat/accounts` | `/settings/wechat/accounts` | `createWechatAccount()` |
| `DELETE /api/wechat/accounts/:id` | `/settings/wechat/accounts` | `deleteWechatAccount()` |
| `POST /api/wechat/accounts/:id/crawl` | `/settings/wechat/accounts` | `crawlWechatAccount()` |
| `GET /api/wechat/tasks` | `/settings/wechat/tasks` | `fetchWechatTasks()` |
| `POST /api/wechat/tasks` | `/settings/wechat/tasks` | `createWechatTask()` |
| `POST /api/wechat/tasks/:id/run` | `/settings/wechat/tasks` | `runWechatTask()` |
| `GET /api/wechat/crawl/status` | 多个页面 | `fetchWechatCrawlStatus()` |

### 7.2 前端组件清单

| 组件 | 位置 | 功能 |
|------|------|------|
| `CookieManager` | `/settings/wechat/page.tsx` | Cookie 管理主页面 |
| `AccountManager` | `/settings/wechat/accounts/page.tsx` | 公众号管理主页面 |
| `TaskManager` | `/settings/wechat/tasks/page.tsx` | 定时任务管理主页面 |
| `WechatSourceFilter` | `/components/articles/WechatSourceFilter.tsx` | 文章列表信源筛选 |
| `CrawlProgressDialog` | `/components/wechat/CrawlProgressDialog.tsx` | 爬取进度对话框 |

### 7.3 前端 API 客户端

```typescript
// frontend/src/lib/api.ts 新增

// Wechat Cookie API
export async function fetchWechatCookies(): Promise<WechatCookie[]>
export async function createWechatCookie(data: CreateWechatCookieRequest): Promise<WechatCookie>
export async function deleteWechatCookie(id: string): Promise<void>
export async function activateWechatCookie(id: string): Promise<void>
export async function validateWechatCookie(id: string): Promise<ValidateResult>

// Wechat Account API
export async function fetchWechatAccounts(): Promise<WechatAccount[]>
export async function createWechatAccount(data: CreateWechatAccountRequest): Promise<WechatAccount>
export async function deleteWechatAccount(id: string): Promise<void>
export async function crawlWechatAccount(id: string): Promise<CrawlTask>

// Wechat Task API
export async function fetchWechatTasks(): Promise<WechatTask[]>
export async function createWechatTask(data: CreateWechatTaskRequest): Promise<WechatTask>
export async function runWechatTask(id: string): Promise<void>
export async function toggleWechatTask(id: string): Promise<void>

// Wechat Crawl Status API
export async function fetchWechatCrawlStatus(): Promise<CrawlStatus>
```

---

## 八、测试验收标准

### 8.1 功能验收

| 功能 | 验收标准 | 测试方法 |
|------|----------|----------|
| Cookie 导入 | 支持 JSON 格式导入 | 导入有效 Cookie 并验证 |
| Cookie 验证 | 能检测 Cookie 是否有效 | 验证过期 Cookie |
| 公众号添加 | 能添加公众号并保存 | 添加后查看列表 |
| 公众号爬取 | 能获取文章完整内容 | 爬取后查看文章内容 |
| LLM 提取 | 自动提取标签、摘要 | 检查文章 tags、summary |
| 文章保存 | 统一存入 articles 表 | 查询 source_type='wechat' |
| KG 抽取 | 自动触发实体关系抽取 | 检查 kg_status='success' |
| 定时爬取 | 按配置时间自动执行 | 检查任务执行日志 |
| 统一展示 | 文章列表支持按信源筛选 | 筛选公众号文章 |

### 8.2 性能验收

| 指标 | 目标 | 测试方法 |
|------|------|----------|
| 单篇文章处理时间 | < 30 秒 | 计时测试 |
| 批量爬取吞吐量 | > 10 篇/分钟 | 批量测试 |
| KG 抽取成功率 | > 95% | 统计分析 |

### 8.3 代码验收

| 指标 | 目标 |
|------|------|
| 单元测试覆盖率 | > 80% |
| 代码规范 | 通过 ESLint/Prettier 检查 |
| 文档完整性 | API 文档 + 使用指南 |

---

## 九、风险与应对

| 风险 | 影响 | 应对方案 |
|------|------|----------|
| 微信 Cookie 过期 | 无法爬取 | 实现有效性检测，过期前提醒用户 |
| 微信反爬 | 被封禁 | 多账号轮换、请求间隔随机化 |
| MediaCrawler 兼容性 | 功能异常 | 隔离在 vendor 目录，不影响现有代码 |
| 前端样式冲突 | UI 异常 | 使用独立页面，复用现有组件库 |

---

## 十、回滚方案

### 10.1 Git 回滚点

```bash
# 当前回滚点
commit: df99278
message: feat: 添加配置一致性检测与实体类型标注优化
branch: master
```

### 10.2 回滚步骤

如果需要回滚到当前状态：

```bash
# 1. 切换到 master 分支
git checkout master

# 2. 丢弃公众号爬取功能的所有更改
git reset --hard df99278

# 3. 删除功能分支（如果存在）
git branch -D feature/wechat-crawler
```

### 10.3 代码隔离策略

1. **新建功能分支**：所有公众号爬取功能在 `feature/wechat-crawler` 分支开发
2. **独立模块目录**：公众号代码放在 `backend/app/services/wechat/` 和 `backend/vendor/mediacrawler/`
3. **前端独立页面**：使用 `/settings/wechat` 路径，不影响现有页面
4. **数据库迁移脚本**：使用独立的迁移文件，可单独回滚

---

## 十一、进度跟踪

### 11.1 里程碑

| 里程碑 | 预计完成日期 | 实际完成日期 | 状态 |
|--------|--------------|--------------|------|
| 后端基础模块 | - | - | ⏳ 待开始 |
| 内容处理管道 | - | - | ⏳ 待开始 |
| 定时任务集成 | - | - | ⏳ 待开始 |
| 前端界面开发 | - | - | ⏳ 待开始 |
| 测试验收 | - | - | ⏳ 待开始 |

### 11.2 更新日志

| 日期 | 更新内容 | 更新人 |
|------|----------|--------|
| 2026-07-30 | 创建初始计划文档 | Claude |

---

## 附录

### A. 技术参考

- [MediaCrawler GitHub](https://github.com/NanmiCoder/MediaCrawler)
- [Playwright Python 文档](https://playwright.dev/python/)
- [APScheduler 文档](https://apscheduler.readthedocs.io/)

### B. 相关文档

- `docs/README.md` - 项目主文档
- `backend/README.md` - 后端文档
- `frontend/README.md` - 前端文档

---

**文档结束**
