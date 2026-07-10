# 知识图谱与文档管理一致性设计

**日期**: 2026-07-09
**状态**: 已批准,待实现
**主源**: 文档管理(SQLite),知识图谱(Neo4j)是衍生视图

## 1. 背景与问题

### 当前架构

- **文档管理** 存储在 SQLite(`articles` 等表),由 `app/api/articles.py` 提供 CRUD。
- **知识图谱** 存储在 Neo4j,由 `app/services/kg/graph.py` 与 `app/api/kg.py` 维护。
- 文章元数据、关键词、来源、分类、状态等"事实"在 SQLite,实体、关系在 Neo4j。
- **Neo4j 不是 Scraping 流程的一部分**:爬取后只写 SQLite,KG 需要用户手动点 `batch-process`。

### 现有不一致问题

| 编号 | 现象 | 根本原因 |
|---|---|---|
| 1 | 文档管理与知识图谱文章数对不上 | 文档管理新增/删除/批量删除文章时,从不调用 Neo4j |
| 2 | 文章更新后,KG 里的 Article 节点 title/summary 是旧的 | `PUT /api/articles/{id}` 不写 Neo4j |
| 3 | 删除文章后,Neo4j 残留 Article 节点和边 | `DELETE /api/articles/{id}` 不调用 `delete_article_kg` |
| 4 | 批量删除文章后,KG 大量残留 | `POST /api/articles/batch-delete` 不级联 |
| 5 | 新爬取的文章不进入图谱 | `scrape-result`/`batch` 不调实体抽取 |
| 6 | 不知道哪些文章已经抽过实体 | `Article` 表无 `kg_status` 标记 |
| 7 | 抽取失败静默,不重试 | `batch_process_articles` 把错误只记到 `errors` 数组 |
| 8 | 无对账机制,漂移无法发现 | 没有定时任务对照两个存储 |

### 目标

> 以文档管理为最终口径,知识图谱是衍生视图。任何时刻:
> `COUNT(:Article in Neo4j) == COUNT(Article in SQLite WHERE status='success')`

并满足:
- Article 节点 metadata(title / url / summary / content_hash / kg_status)与 SQLite 实时一致
- 实体的抽取是异步(不阻塞 CRUD 接口),失败可重试
- 重新抽取仅由用户手动触发(明确意图,避免频繁调 LLM)
- 提供对账工具,能发现并修复漂移

## 2. 架构与数据流

```
┌─────────────────────────────────────────────────────────────┐
│  文档管理 (SQLite, Source of Truth)                         │
│  Article + Category + ScrapeSource + Keyword + ArticleLink  │
│  + 新增: kg_status, kg_processed_at, kg_content_hash        │
│      + kg_error_message                                     │
└──────┬───────────────────┬──────────────────┬───────────────┘
       │ create            │ update           │ delete
       ↓                   ↓                  ↓
   ┌───────────────────────────────────────────────┐
   │  articles.py endpoint 调用 kg_sync.*          │
   │  - upsert_article_metadata (同步,毫秒级)      │
   │  - background: extract_and_link_entities      │
   │  - delete_article_full (同步,毫秒级)          │
   └──────┬───────────────────┬──────────────────┘
          │                   │
          ↓                   ↓
   ┌──────────────────────────────────────┐
   │  Neo4j (KG, 衍生视图)                │
   │  (a:Article {id, title, url, summary,│
   │     content_hash, kg_status,         │
   │     updated_at})                     │
   │  (a)-[:CONTAINS_ENTITY]->(e)        │
   │  (e1)-[:RELATES_TO {rel_type}]->(e2)│
   └──────────────────────────────────────┘
          ↑
          │ reconcile (POST /api/kg/reconcile)
          │
   ┌──────┴───────────────────────────────────────┐
   │  对账逻辑:                                    │
   │  1. SQLite 有 & KG 没有 → 异步抽实体          │
   │  2. KG 有 & SQLite 没有 → 删 Article 节点     │
   │  3. content_hash 变了 → 标 dirty,提示重抽     │
   └──────────────────────────────────────────────┘
```

### 核心不变量

- **N1**: `MATCH (a:Article) RETURN count(a)` 永远等于 `SELECT count(*) FROM articles WHERE status='success'`(以文档管理为最终口径)
- **N2**: Article 节点的 title/url/summary 与 SQLite 中该文章的最新字段一致
- **N3**: 一次 CRUD 完成后,SQLite 的 `kg_status` 与 Neo4j Article 节点的 `kg_status` 一致
- **N4**: 删除 SQLite 文章后,Neo4j 中对应的 Article 节点、C:CONTAINS_ENTITY 边、不再被引用的 Entity 全部清空
- **N5**: 实体抽取失败不会阻塞 CRUD 接口

## 3. 数据库 schema 增量

### `articles` 表新增字段

```python
# app/models/article.py 新增字段
kg_status: Mapped[str] = mapped_column(
    String(20), default="pending", index=True
)
# 取值: pending / processing / success / failed

kg_processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

kg_content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
# Article.content 的 SHA-256,用于判断"内容是否变了"

kg_error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
# 最近一次失败的错误信息
```

### Neo4j Article 节点补充字段

```cypher
(a:Article {
  id,           // 主键,与 SQLite Article.id 一致
  title,
  url,
  summary,
  content_hash, // 冗余自 SQLite,便于 reconcile 比对
  kg_status,    // 冗余自 SQLite,便于 KG 页面直接展示
  updated_at    // 上一次 metadata 同步时间(datetime())
})
```

冗余 `content_hash` 与 `kg_status` 的理由:
- reconcile / KG 页面展示需要这些字段,不必每次都 join 回 SQLite
- 写入路径固定(只在 kg_sync.* 中写),不会产生不一致

### 迁移

新增 `scripts/migrate_kg_status.py`:
- 幂等地 `ALTER TABLE articles ADD COLUMN ...`(用 try/except 包装)
- 现有 `Article.content_hash` 已有,直接复制到 `kg_content_hash`
- 现有文章若 KG 中已有 Article 节点 → `kg_status='success'`,否则 `pending`
- 写日志,告知用户跑一次 reconcile 修复漂移

## 4. API 改动

### 4.1 文档管理 API(`app/api/articles.py`)

| Endpoint | 改动 |
|---|---|
| `POST /api/articles` | 创建事务 commit 后,调用 `kg_sync.on_article_created(article, background_tasks)` |
| `PUT /api/articles/{id}` | commit 后,调用 `kg_sync.on_article_updated(article, background_tasks)`(只更新 metadata;若 content_hash 变了,设 `kg_status='pending'`) |
| `DELETE /api/articles/{id}` | 删前先调 `kg_sync.on_article_deleted(article_id)` |
| `POST /api/articles/batch-delete` | 循环里逐个 `kg_sync.on_article_deleted(aid)`,失败累计到 errors |
| `POST /api/articles/scrape-result` | commit 后追加 `kg_sync.on_article_created(article, background_tasks)` |
| `POST /api/articles/batch` | 同上,逐个调用 |
| `GET /api/articles` | 响应序列化加上 `kg_status`、`kg_processed_at`、`kg_error_message` |

### 4.2 知识图谱 API(`app/api/kg.py`)

| Endpoint | 行为 |
|---|---|
| `POST /api/kg/reconcile` | 返回 `{missing_in_kg, orphan_in_kg, dirty_in_kg, fixed_summary}`;`?apply=true` 时自动修复(异步) |
| `POST /api/kg/reprocess/{article_id}` | 清旧实体+关系,重新走 `extract_and_link_entities`,同步等待结果 |
| `GET /api/kg/article/{article_id}/status` | 返回 `{kg_status, kg_processed_at, kg_error_message, entity_count, relation_count}`(用于前端轮询) |
| `GET /api/kg/stats` | 响应中加 `articles_in_db`(SQLite count)与 `articles_in_kg`(Neo4j count),若不等加 `drift_detected=true` |

### 4.3 Neo4jService(`app/services/kg/graph.py`)新增

```python
async def upsert_article_metadata(
    article_id: str, title: str, url: str, summary: str,
    content_hash: str, kg_status: str
) -> bool:
    """同步 Article 节点 metadata,不触发实体抽取"""

async def delete_article_full(article_id: str) -> bool:
    """彻底删:Article 节点 + CONTAINS_ENTITY 边 + 孤儿 Entity"""

async def find_orphan_articles(sqlite_ids: set[str]) -> list[str]:
    """返回 Neo4j 中存在但不在 sqlite_ids 集合的 Article.id"""

async def find_dirty_articles(article_pairs: list[tuple[str, str, str]]) -> list[str]:
    """入参 (article_id, sqlite_hash, kg_hash),返回 hash 不一致的文章 id"""
```

### 4.4 新模块 `app/services/kg_sync.py`

```python
# 服务编排层,把"文档管理 → 知识图谱"的所有动作集中
async def on_article_created(article: Article, bg: BackgroundTasks) -> None
async def on_article_updated(article: Article, bg: BackgroundTasks) -> None
async def on_article_deleted(article_id: str) -> None
async def extract_and_link_entities(article_id: str) -> None  # 同步版本,供 bg 和 reconcile 复用
async def reconcile(apply: bool = False) -> dict  # 对账
```

### 4.5 前端改动

| 页面 | 改动 |
|---|---|
| 文章列表 | 每行加 "已入图谱 / 抽取中 / 失败 / 未抽取" 角标;失败/未抽取的加 "重抽" 按钮(POST `/api/kg/reprocess/{id}`) |
| 知识图谱页 | 顶部加 "对账" 按钮(POST `/api/kg/reconcile?apply=true`);显示"文档管理 X 篇 / 图谱 Y 篇",差异高亮 |

## 5. 错误处理

| 场景 | 行为 |
|---|---|
| Neo4j 不可用 | SQLite 文章已落库 → `kg_status='failed'`,不回滚文档管理(以文档管理为最终口径)。返回 200,响应加 `kg_warning: "kg sync failed, will retry via reconcile"` |
| LLM 抽取失败 | Background task 捕获异常 → `kg_status='failed'` + `kg_error_message` 写 SQLite,不抛给用户 |
| 类型不一致(Article id) | 两边都用字符串 UUID,冲突时以 SQLite 为准;reconcile 删 Neo4j 多余节点 |
| 事务边界 | SQLite `commit` 之后再调 Neo4j;Neo4j 失败不影响 SQLite 已写入的数据 |
| 并发 | kg_sync 函数不持锁;Background task 并发抽取多个文章,Neo4j driver 自身支持并发 |
| 重抽幂等 | `reprocess/{id}` 先删 Article 节点 + 旧 CONTAINS_ENTITY 边 + 孤儿 Entity,再走标准流程,失败可重试 |
| LLM 限流 | Background task 抽取时 `await asyncio.sleep(0.5)`,reconcile 批量补抽时同 |

## 6. 测试策略(TDD)

### 6.1 单元测试

1. `test_kg_sync_upsert.py` — 验证 `upsert_article_metadata` 在 Neo4j 中创建/更新 Article 节点
2. `test_kg_sync_delete.py` — 验证 `delete_article_full` 清掉 Article 节点、边、孤儿 Entity(但保留仍被引用的 Entity)
3. `test_kg_sync_reconcile.py` — 制造 3 种漂移(缺失/孤儿/脏),断言 reconcile 返回值与修复结果
4. `test_kg_sync_reprocess.py` — 验证重抽清旧建新,失败可重试

### 6.2 集成测试

5. `test_article_kg_integration.py` — 端到端:articles.py 增/改/删 → Neo4j 状态变化 → KG stats 正确
6. `test_scrape_to_kg.py` — `POST /api/articles/scrape-result` → 触发后台抽取 → 等 1 秒 → Neo4j 出现 CONTAINS_ENTITY 边

### 6.3 回归测试

7. 跑已有 `backend/tests/` 全套,确保 `process_article` 等旧 API 行为不变
8. 跑 frontend `npm run build`,确保类型/语法 OK

### 6.4 测试环境

- 使用 docker-compose 起一个临时的 Neo4j + 内存 SQLite(若可行)或单独的测试 DB
- 每次 test setUp 清空 Neo4j 节点

## 7. 实施步骤(粗)

1. **Step 1**: 写 `migrate_kg_status.py` + 加 Article 字段,跑迁移
2. **Step 2**: 写 `kg_sync` 模块 + Neo4jService 新方法,先写测试再写实现(TDD)
3. **Step 3**: 改 articles.py 5 个 endpoint + scrape.py 2 个,接 kg_sync
4. **Step 4**: 加 `reconcile` / `reprocess` / `status` 三个 KG endpoint
5. **Step 5**: scheduler.py 加可选定时对账任务(默认关闭)
6. **Step 6**: 前端文章列表 + KG 页面改造
7. **Step 7**: 跑全量回归 + 手动跑一次 reconcile 看效果

## 8. 不在范围(明确排除)

- ❌ 不重写 EntityExtractor(已有够用)
- ❌ 不重写 Article 模型的字段类型
- ❌ 不加新的微服务(保持单 FastAPI 进程)
- ❌ 不引入消息队列(RQ/Celery),BackgroundTasks 已够用
- ❌ 不支持实时推送(前端轮询 `/api/kg/article/{id}/status` 即可)
- ❌ 不动 Scraping 流程的字段定义,只追加 KG 触发逻辑
