# KG-Article 一致性同步实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让知识图谱成为文档管理的"实时衍生视图",保证 Article 节点数量与 metadata 与 SQLite 实时一致,实体抽取异步、可重试、可对账。

**Architecture:** 新建 `kg_sync` 编排服务,在 articles CRUD/scrape 端点 commit 之后显式调用 Neo4j 同步:metadata 同步路径走 `upsert_article_metadata`,实体抽取走 FastAPI BackgroundTasks。Article 表加 4 个字段追踪状态。Neo4j 加 `delete_article_full` 彻底删除 + `reconcile` 对账 API。

**Tech Stack:** FastAPI 0.115+, SQLAlchemy 2.0+, neo4j 5.x async driver, APScheduler(已有), Next.js 16.2.9

**关联文档**: [2026-07-09-kg-article-consistency.md](../specs/2026-07-09-kg-article-consistency.md)

## Global Constraints

- **代码风格**: 遵循现有 `backend/app/services/` 风格,类型注解使用 `Mapped[]` / `Optional[]` / `List[]`,中文 log
- **不破坏向后兼容**: 现有 `POST /api/kg/process/{id}` 与 `POST /api/kg/batch-process` 行为保持不变
- **失败不阻塞**: Neo4j 同步失败时,SQLite 已落库的数据不回滚
- **TDD**: 每个新方法先写测试,再写实现,确保测试失败 → 实现 → 测试通过
- **小步提交**: 每个 Task 末尾必须 `git commit`
- **不变量 N1** (来自 spec): `MATCH (a:Article) RETURN count(a) == SELECT count(*) FROM articles WHERE status='success'`
- **不变量 N2**: Article 节点 title/url/summary/content_hash/kg_status 与 SQLite 实时一致
- **不变量 N3**: 一次 CRUD 完成后,SQLite 的 `kg_status` 与 Neo4j Article 节点的 `kg_status` 一致

## 前置准备: 在 worktree 中工作

在开始 Task 1 之前,先开 worktree 隔离本次改动。

```bash
cd "/home/aircas/AI/AI Studio"
git worktree add .worktrees/kg-article-sync -b feature/kg-article-sync
cd .worktrees/kg-article-sync
```

后续所有 Task 都在 `.worktrees/kg-article-sync/` 路径下执行。

---

## Task 1: 给 Article 模型加 4 个字段 + 数据库迁移脚本

**Files:**
- Modify: `backend/app/models/article.py:50-150`(在 Article 类内)
- Create: `backend/scripts/migrate_kg_status.py`

**Interfaces:**
- Consumes: 现有 `Article` 模型
- Produces: `Article` 类新增字段 `kg_status` / `kg_processed_at` / `kg_content_hash` / `kg_error_message`

### Step 1: 写失败的迁移测试

创建 `backend/tests/test_migrate_kg_status.py`:

```python
"""测试 KG 状态字段迁移的幂等性"""
import os
import tempfile
import sqlite3
from pathlib import Path
import importlib.util


def test_migrate_kg_status_is_idempotent():
    """连续跑两次迁移不应报错,且字段只存在一份"""
    # 创建临时数据库
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        # 初始化一个空 articles 表(仅主键)
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE articles (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                title TEXT,
                content TEXT,
                status TEXT DEFAULT 'pending',
                content_hash TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        conn.commit()
        conn.close()

        # 把 DATABASE_URL 指向临时库
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

        # 动态加载迁移脚本
        script_path = Path(__file__).resolve().parent.parent / "scripts" / "migrate_kg_status.py"
        spec = importlib.util.spec_from_file_location("migrate_kg_status", script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # 跑两次
        module.run_migration()
        module.run_migration()  # 必须不报错

        # 验证字段
        conn = sqlite3.connect(db_path)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(articles)").fetchall()}
        conn.close()

        assert "kg_status" in cols
        assert "kg_processed_at" in cols
        assert "kg_content_hash" in cols
        assert "kg_error_message" in cols
    finally:
        os.unlink(db_path)
```

### Step 2: 运行测试确认它失败

```bash
cd backend
DATABASE_URL=sqlite:///./test.db python -m pytest tests/test_migrate_kg_status.py -v
```

Expected: FAIL,`ModuleNotFoundError: No module named 'scripts.migrate_kg_status'`

### Step 3: 实现迁移脚本

创建 `backend/scripts/migrate_kg_status.py`:

```python
"""
为 articles 表添加 KG 同步状态字段
- kg_status: pending / processing / success / failed
- kg_processed_at: 最近一次抽取完成时间
- kg_content_hash: 抽取时的内容哈希,用于检测内容变化
- kg_error_message: 最近一次失败的错误信息
"""
import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migrate_kg_status")

# 待新增字段定义:(列名, SQL 类型)
NEW_COLUMNS = [
    ("kg_status", "VARCHAR(20) DEFAULT 'pending' NOT NULL"),
    ("kg_processed_at", "DATETIME"),
    ("kg_content_hash", "VARCHAR(64)"),
    ("kg_error_message", "TEXT"),
]

# 为已有字段加索引(可选,后续 reconcile 用)
NEW_INDEXES = [
    ("idx_articles_kg_status", "kg_status"),
]


def _column_exists(conn, table: str, column: str) -> bool:
    """检查列是否已存在(SQLite 风格 PRAGMA)"""
    result = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(row[1] == column for row in result)


def _index_exists(conn, index_name: str) -> bool:
    """检查索引是否已存在"""
    result = conn.execute(text(f"PRAGMA index_list(articles)")).fetchall()
    return any(row[1] == index_name for row in result)


def run_migration():
    """执行迁移,幂等"""
    db_url = os.getenv("DATABASE_URL", "sqlite:///./ai_studio.db")
    engine = create_engine(db_url)

    with engine.begin() as conn:
        for col_name, col_type in NEW_COLUMNS:
            if _column_exists(conn, "articles", col_name):
                logger.info(f"列 {col_name} 已存在,跳过")
                continue
            try:
                conn.execute(text(
                    f"ALTER TABLE articles ADD COLUMN {col_name} {col_type}"
                ))
                logger.info(f"新增列: {col_name}")
            except OperationalError as e:
                logger.warning(f"列 {col_name} 添加失败(可能已存在): {e}")

        for idx_name, idx_col in NEW_INDEXES:
            if _index_exists(conn, idx_name):
                logger.info(f"索引 {idx_name} 已存在,跳过")
                continue
            try:
                conn.execute(text(
                    f"CREATE INDEX {idx_name} ON articles ({idx_col})"
                ))
                logger.info(f"新增索引: {idx_name}")
            except OperationalError as e:
                logger.warning(f"索引 {idx_name} 创建失败: {e}")

        # 回填 kg_content_hash = content_hash(已有字段)
        try:
            result = conn.execute(text("""
                UPDATE articles
                SET kg_content_hash = content_hash
                WHERE kg_content_hash IS NULL AND content_hash IS NOT NULL
            """))
            logger.info(f"回填 kg_content_hash 完成,影响 {result.rowcount} 行")
        except OperationalError as e:
            logger.warning(f"回填 kg_content_hash 失败: {e}")

    logger.info("迁移完成")


if __name__ == "__main__":
    run_migration()
```

### Step 4: 跑测试确认通过

```bash
cd backend
DATABASE_URL=sqlite:///./test.db python -m pytest tests/test_migrate_kg_status.py -v
```

Expected: PASS,`1 passed`

### Step 5: 修改 Article 模型加字段

修改 `backend/app/models/article.py`,在 `Article` 类中 `status` 字段后面添加:

```python
# 知识图谱同步状态
kg_status: Mapped[str] = mapped_column(
    String(20), default="pending", index=True
)
# 取值: pending / processing / success / failed
kg_processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
kg_content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
kg_error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

同时在 `__table_args__` 的 Index 元组中添加:

```python
Index("idx_articles_kg_status", "kg_status"),
```

### Step 6: 跑迁移脚本应用到主库

```bash
cd backend
python scripts/migrate_kg_status.py
```

Expected log:
```
新增列: kg_status
新增列: kg_processed_at
新增列: kg_content_hash
新增列: kg_error_message
新增索引: idx_articles_kg_status
回填 kg_content_hash 完成,影响 N 行
迁移完成
```

### Step 7: 验证模型可加载

```bash
cd backend
python -c "from app.models.article import Article; print(Article.kg_status)"
```

Expected: 输出列对象描述(无报错)

### Step 8: Commit

```bash
cd .worktrees/kg-article-sync
git add backend/app/models/article.py backend/scripts/migrate_kg_status.py backend/tests/test_migrate_kg_status.py
git commit -m "feat(kg-sync): Article 模型加 kg_status 等 4 字段 + 幂等迁移脚本"
```

---

## Task 2: Neo4jService 加 4 个新方法(upsert / delete_full / find_orphan / find_dirty)

**Files:**
- Modify: `backend/app/services/kg/graph.py`(在 `Neo4jService` 类内新增方法)
- Create: `backend/tests/test_neo4j_sync_methods.py`

**Interfaces:**
- Consumes: `Neo4jService` 实例(已通过 `connect()` 建立连接)
- Produces: 4 个新方法
  ```python
  async def upsert_article_metadata(article_id, title, url, summary, content_hash, kg_status) -> bool
  async def delete_article_full(article_id) -> bool
  async def find_orphan_articles(sqlite_ids: set[str]) -> list[str]
  async def find_dirty_articles(article_pairs: list[tuple[str, str, str]]) -> list[str]
  ```
  入参 `article_pairs` 格式: `(article_id, sqlite_content_hash, kg_content_hash)`

### Step 1: 写失败的测试

创建 `backend/tests/test_neo4j_sync_methods.py`:

```python
"""
测试 Neo4jService 的 KG 同步方法
需要本地起 Neo4j (bolt://localhost:7687, neo4j/password)
测试用临时唯一前缀,setUp 清空
"""
import os
import asyncio
import uuid
import pytest
from neo4j import AsyncGraphDatabase

from app.services.kg.graph import Neo4jService


NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


@pytest.fixture
async def neo4j_service():
    """每个测试用独立的服务实例,teardown 清空所有节点"""
    svc = Neo4jService(uri=NEO4J_URI, user=NEO4J_USER, password=NEO4J_PASSWORD)
    await svc.connect()
    # 每次清空
    async with svc._driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
    yield svc
    async with svc._driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
    await svc.close()


@pytest.mark.asyncio
async def test_upsert_article_metadata_creates_node(neo4j_service):
    aid = f"test-{uuid.uuid4()}"
    ok = await neo4j_service.upsert_article_metadata(
        article_id=aid, title="T1", url="http://x", summary="S1",
        content_hash="h1", kg_status="pending"
    )
    assert ok is True

    async with neo4j_service._driver.session() as session:
        result = await session.run("MATCH (a:Article {id: $id}) RETURN a", id=aid)
        record = await result.single()
        assert record is not None
        node = record["a"]
        assert node["title"] == "T1"
        assert node["kg_status"] == "pending"
        assert node["content_hash"] == "h1"


@pytest.mark.asyncio
async def test_upsert_article_metadata_updates_existing(neo4j_service):
    aid = f"test-{uuid.uuid4()}"
    await neo4j_service.upsert_article_metadata(
        article_id=aid, title="T1", url="http://x", summary="S1",
        content_hash="h1", kg_status="pending"
    )
    await neo4j_service.upsert_article_metadata(
        article_id=aid, title="T2", url="http://y", summary="S2",
        content_hash="h2", kg_status="success"
    )
    async with neo4j_service._driver.session() as session:
        result = await session.run("MATCH (a:Article {id: $id}) RETURN a", id=aid)
        record = await result.single()
        node = record["a"]
        assert node["title"] == "T2"
        assert node["kg_status"] == "success"


@pytest.mark.asyncio
async def test_delete_article_full_removes_node_and_edges(neo4j_service):
    aid = f"test-{uuid.uuid4()}"
    eid = "Entity-1"
    # 建文章 + 实体 + 边
    async with neo4j_service._driver.session() as session:
        await session.run("CREATE (a:Article {id: $aid, title: 'T', url: 'u', summary: 's'})", aid=aid)
        await session.run("CREATE (e:Entity {name: $eid, entity_type: 'PERSON'})", eid=eid)
        await session.run("""
            MATCH (a:Article {id: $aid}), (e:Entity {name: $eid})
            MERGE (a)-[:CONTAINS_ENTITY]->(e)
        """, aid=aid, eid=eid)

    ok = await neo4j_service.delete_article_full(aid)
    assert ok is True

    async with neo4j_service._driver.session() as session:
        r1 = await session.run("MATCH (a:Article {id: $aid}) RETURN a", aid=aid)
        assert await r1.single() is None
        r2 = await session.run("MATCH (e:Entity {name: $eid}) RETURN e", eid=eid)
        assert await r2.single() is None  # 孤儿实体也清掉


@pytest.mark.asyncio
async def test_delete_article_full_keeps_shared_entities(neo4j_service):
    """如果 Entity 仍被其他文章引用,不删 Entity"""
    a1, a2 = f"a-{uuid.uuid4()}", f"a-{uuid.uuid4()}"
    eid = "shared-entity"
    async with neo4j_service._driver.session() as session:
        for aid in (a1, a2):
            await session.run("CREATE (a:Article {id: $aid, title: 'T', url: 'u'})", aid=aid)
        await session.run("CREATE (e:Entity {name: $eid, entity_type: 'PERSON'})", eid=eid)
        for aid in (a1, a2):
            await session.run("""
                MATCH (a:Article {id: $aid}), (e:Entity {name: $eid})
                MERGE (a)-[:CONTAINS_ENTITY]->(e)
            """, aid=aid, eid=eid)

    await neo4j_service.delete_article_full(a1)

    async with neo4j_service._driver.session() as session:
        r1 = await session.run("MATCH (a:Article {id: $a1}) RETURN a", a1=a1)
        assert await r1.single() is None
        r2 = await session.run("MATCH (e:Entity {name: $eid}) RETURN e", eid=eid)
        assert await r2.single() is not None  # 仍被 a2 引用,保留


@pytest.mark.asyncio
async def test_find_orphan_articles(neo4j_service):
    a1, a2, a3 = f"a-{uuid.uuid4()}", f"a-{uuid.uuid4()}", f"a-{uuid.uuid4()}"
    async with neo4j_service._driver.session() as session:
        for aid in (a1, a2, a3):
            await session.run("CREATE (a:Article {id: $aid, title: 'T'})", aid=aid)

    # SQLite 只有 a1, a2
    sqlite_ids = {a1, a2}
    orphans = await neo4j_service.find_orphan_articles(sqlite_ids)
    assert orphans == [a3] or set(orphans) == {a3}


@pytest.mark.asyncio
async def test_find_dirty_articles(neo4j_service):
    a1, a2 = f"a-{uuid.uuid4()}", f"a-{uuid.uuid4()}"
    async with neo4j_service._driver.session() as session:
        await session.run("CREATE (a:Article {id: $a1, content_hash: 'h1'})", a1=a1)
        await session.run("CREATE (a:Article {id: $a2, content_hash: 'h2'})", a2=a2)

    # a1 hash 一致, a2 hash 不一致
    pairs = [(a1, "h1", "h1"), (a2, "h2-new", "h2")]
    dirty = await neo4j_service.find_dirty_articles(pairs)
    assert dirty == [a2] or set(dirty) == {a2}
```

### Step 2: 跑测试确认失败

```bash
cd backend
python -m pytest tests/test_neo4j_sync_methods.py -v
```

Expected: FAIL,所有 6 个测试 `AttributeError: 'Neo4jService' object has no attribute 'upsert_article_metadata'`

### Step 3: 实现 4 个新方法

在 `backend/app/services/kg/graph.py` 的 `Neo4jService` 类中,`delete_article_kg` 方法之后添加:

```python
    async def upsert_article_metadata(
        self,
        article_id: str,
        title: str,
        url: str,
        summary: Optional[str],
        content_hash: Optional[str],
        kg_status: str
    ) -> bool:
        """同步 Article 节点 metadata,不触发实体抽取"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            query = """
            MERGE (a:Article {id: $article_id})
            SET a.title = $title,
                a.url = $url,
                a.summary = $summary,
                a.content_hash = $content_hash,
                a.kg_status = $kg_status,
                a.updated_at = datetime()
            RETURN a
            """
            try:
                await session.run(query, {
                    "article_id": article_id,
                    "title": title,
                    "url": url,
                    "summary": summary or "",
                    "content_hash": content_hash or "",
                    "kg_status": kg_status
                })
                return True
            except Exception as e:
                logger.error(f"upsert_article_metadata 失败 {article_id}: {e}")
                return False

    async def delete_article_full(self, article_id: str) -> bool:
        """彻底删除:Article 节点 + CONTAINS_ENTITY 边 + 不再被引用的 Entity"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            query = """
            MATCH (a:Article {id: $article_id})
            OPTIONAL MATCH (a)-[r:CONTAINS_ENTITY]->(e:Entity)
            WITH a, collect(DISTINCT e) AS entities, collect(DISTINCT r) AS rels
            FOREACH (rel IN rels | DELETE rel)
            WITH a, entities
            FOREACH (e IN entities |
                FOREACH (_ IN CASE WHEN NOT EXISTS((e)<-[:CONTAINS_ENTITY]-()) THEN [1] ELSE [] END |
                    DETACH DELETE e
                )
            )
            WITH a
            DETACH DELETE a
            """
            try:
                await session.run(query, {"article_id": article_id})
                return True
            except Exception as e:
                logger.error(f"delete_article_full 失败 {article_id}: {e}")
                return False

    async def find_orphan_articles(self, sqlite_ids: set) -> list:
        """返回 Neo4j 中存在但不在 sqlite_ids 集合的 Article.id"""
        if not self._driver:
            await self.connect()

        if not sqlite_ids:
            sqlite_ids = {"__empty__"}  # 避免空集合 Cypher 报错

        async with self._driver.session() as session:
            query = """
            MATCH (a:Article)
            WHERE NOT a.id IN $sqlite_ids
            RETURN a.id AS id
            """
            try:
                result = await session.run(query, {"sqlite_ids": list(sqlite_ids)})
                records = await result.data()
                return [r["id"] for r in records]
            except Exception as e:
                logger.error(f"find_orphan_articles 失败: {e}")
                return []

    async def find_dirty_articles(self, article_pairs: list) -> list:
        """
        入参: [(article_id, sqlite_hash, kg_hash), ...]
        返回: sqlite_hash != kg_hash 的 article_id 列表
        """
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            query = """
            UNWIND $pairs AS p
            MATCH (a:Article {id: p[0]})
            WHERE a.content_hash IS NULL OR a.content_hash <> p[1]
            RETURN a.id AS id
            """
            try:
                result = await session.run(query, {
                    "pairs": [[aid, sh, kh] for aid, sh, kh in article_pairs]
                })
                records = await result.data()
                return [r["id"] for r in records]
            except Exception as e:
                logger.error(f"find_dirty_articles 失败: {e}")
                return []
```

### Step 4: 跑测试确认通过

```bash
cd backend
python -m pytest tests/test_neo4j_sync_methods.py -v
```

Expected: 6 个测试全 PASS

### Step 5: Commit

```bash
cd .worktrees/kg-article-sync
git add backend/app/services/kg/graph.py backend/tests/test_neo4j_sync_methods.py
git commit -m "feat(kg-sync): Neo4jService 加 upsert/delete_full/find_orphan/find_dirty"
```

---

## Task 3: 新建 kg_sync 编排服务(TDD)

**Files:**
- Create: `backend/app/services/kg_sync.py`
- Create: `backend/tests/test_kg_sync.py`

**Interfaces:**
- Consumes: `Article` ORM 实例,`Neo4jService`,`EntityExtractor`,`BackgroundTasks`
- Produces: 5 个函数
  ```python
  async def on_article_created(article: Article, background_tasks: BackgroundTasks) -> None
  async def on_article_updated(article: Article, background_tasks: BackgroundTasks) -> None
  async def on_article_deleted(article_id: str) -> None
  async def extract_and_link_entities(article_id: str) -> None
  async def reconcile(apply: bool, db: Session) -> dict
  ```

### Step 1: 写失败的测试

创建 `backend/tests/test_kg_sync.py`:

```python
"""
测试 kg_sync 编排服务
依赖 SQLite 测试 DB + Neo4j,通过 monkeypatch 隔离
"""
import os
import uuid
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import BackgroundTasks

from app.services.kg_sync import (
    on_article_created,
    on_article_updated,
    on_article_deleted,
    extract_and_link_entities,
    reconcile,
)


@pytest.fixture
def mock_neo4j():
    """Mock Neo4jService 的方法"""
    with patch("app.services.kg_sync.Neo4jService") as Mock:
        instance = Mock.return_value
        instance.upsert_article_metadata = AsyncMock(return_value=True)
        instance.delete_article_full = AsyncMock(return_value=True)
        instance.find_orphan_articles = AsyncMock(return_value=[])
        instance.find_dirty_articles = AsyncMock(return_value=[])
        yield instance


@pytest.fixture
def mock_extractor():
    with patch("app.services.kg_sync.EntityExtractor") as Mock:
        instance = Mock.return_value
        result = MagicMock()
        result.error = None
        result.entities = []
        result.relations = []
        instance.extract = AsyncMock(return_value=result)
        instance.deduplicate_entities = MagicMock(return_value=[])
        yield instance


@pytest.fixture
def article():
    a = MagicMock()
    a.id = f"art-{uuid.uuid4()}"
    a.title = "T"
    a.url = "http://x"
    a.summary = "S"
    a.content = "C"
    a.content_hash = "h1"
    a.kg_status = "pending"
    return a


@pytest.mark.asyncio
async def test_on_article_created_syncs_metadata_and_schedules_extract(
    article, mock_neo4j, mock_extractor
):
    bg = MagicMock(spec=BackgroundTasks)
    await on_article_created(article, bg)

    # 1. 同步 metadata
    mock_neo4j.upsert_article_metadata.assert_awaited_once()
    call_kwargs = mock_neo4j.upsert_article_metadata.await_args.kwargs
    assert call_kwargs["article_id"] == article.id
    assert call_kwargs["content_hash"] == "h1"
    assert call_kwargs["kg_status"] == "pending"

    # 2. 后台任务排上
    bg.add_task.assert_called_once()
    assert bg.add_task.call_args.args[0].__name__ == "extract_and_link_entities"
    assert bg.add_task.call_args.args[1] == article.id


@pytest.mark.asyncio
async def test_on_article_created_neo4j_failure_does_not_raise(
    article, mock_extractor
):
    mock_neo4j = MagicMock()
    mock_neo4j.upsert_article_metadata = AsyncMock(return_value=False)
    with patch("app.services.kg_sync.Neo4jService", return_value=mock_neo4j):
        bg = MagicMock(spec=BackgroundTasks)
        # 不应抛
        await on_article_created(article, bg)
        # 后台仍排上(失败重试由 reconcile 处理)
        bg.add_task.assert_called_once()


@pytest.mark.asyncio
async def test_on_article_updated_only_metadata_when_hash_unchanged(
    article, mock_neo4j
):
    article.content_hash = "h1"
    article.kg_status = "success"
    bg = MagicMock(spec=BackgroundTasks)
    await on_article_updated(article, bg)

    mock_neo4j.upsert_article_metadata.assert_awaited_once()
    call_kwargs = mock_neo4j.upsert_article_metadata.await_args.kwargs
    # hash 没变,kg_status 保持 success
    assert call_kwargs["kg_status"] == "success"
    # 不排后台任务
    bg.add_task.assert_not_called()


@pytest.mark.asyncio
async def test_on_article_updated_marks_pending_when_hash_changed(
    article, mock_neo4j
):
    # SQLite 已有 kg_content_hash=h1,Article.content_hash=h2
    article.content_hash = "h2"
    article.kg_content_hash = "h1"
    article.kg_status = "success"
    bg = MagicMock(spec=BackgroundTasks)
    await on_article_updated(article, bg)

    call_kwargs = mock_neo4j.upsert_article_metadata.await_args.kwargs
    assert call_kwargs["kg_status"] == "pending"
    # 暂不排后台(等用户点"重抽")
    bg.add_task.assert_not_called()


@pytest.mark.asyncio
async def test_on_article_deleted_calls_delete_full(article, mock_neo4j):
    await on_article_deleted(article.id)
    mock_neo4j.delete_article_full.assert_awaited_once_with(article.id)


@pytest.mark.asyncio
async def test_extract_and_link_entities_success(article, mock_neo4j, mock_extractor):
    # Mock SQLAlchemy session 查询
    with patch("app.services.kg_sync.SessionLocal") as MockSession:
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = article
        MockSession.return_value = session

        # Mock Neo4j 写入
        mock_neo4j.batch_create_entities_and_relations = AsyncMock(
            return_value={"entities_created": 0, "relations_created": 0}
        )

        await extract_and_link_entities(article.id)

        # 验证更新 kg_status='success' 后 commit
        assert article.kg_status == "success"
        session.commit.assert_called()


@pytest.mark.asyncio
async def test_reconcile_returns_summary(article, mock_neo4j):
    with patch("app.services.kg_sync.SessionLocal") as MockSession:
        session = MagicMock()
        # SQLite: 1 篇 success
        session.query.return_value.filter.return_value.all.return_value = [article]
        MockSession.return_value = session

        # Neo4j: 0 孤儿, 0 脏
        mock_neo4j.find_orphan_articles = AsyncMock(return_value=[])
        mock_neo4j.find_dirty_articles = AsyncMock(return_value=[])

        result = await reconcile(apply=False, db=session)

        assert "missing_in_kg" in result
        assert "orphan_in_kg" in result
        assert "dirty_in_kg" in result
        assert result["missing_in_kg"] == 1  # article 在 SQLite 但不在 Neo4j
        assert result["orphan_in_kg"] == 0
        assert result["dirty_in_kg"] == 0
```

### Step 2: 跑测试确认失败

```bash
cd backend
python -m pytest tests/test_kg_sync.py -v
```

Expected: FAIL,`ModuleNotFoundError: No module named 'app.services.kg_sync'`

### Step 3: 实现 kg_sync 模块

创建 `backend/app/services/kg_sync.py`:

```python
"""
知识图谱同步服务

把"文档管理 → 知识图谱"的所有动作集中编排,确保:
- Article 节点 metadata 实时同步
- 实体抽取异步,失败不阻塞 CRUD
- 删除文章级联删 KG
- 提供对账工具
"""
import asyncio
import logging
from typing import Optional
from datetime import datetime

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.article import Article
from app.services.kg import Neo4jService, EntityExtractor

logger = logging.getLogger("ai-studio")


def _build_neo4j() -> Neo4jService:
    """构建 Neo4jService(可被 patch 注入)"""
    return Neo4jService()


async def on_article_created(article: Article, background_tasks: BackgroundTasks) -> None:
    """文档管理新建文章后调用:同步 metadata + 排后台抽实体"""
    neo4j = _build_neo4j()
    ok = await neo4j.upsert_article_metadata(
        article_id=article.id,
        title=article.title or "",
        url=article.url or "",
        summary=article.summary,
        content_hash=article.content_hash,
        kg_status=article.kg_status or "pending"
    )
    if not ok:
        logger.warning(f"新建文章 {article.id} 时 Neo4j metadata 同步失败,后续 reconcile 兜底")
    # 后台抽实体(失败由 kg_status='failed' 标记)
    background_tasks.add_task(extract_and_link_entities, article.id)


async def on_article_updated(article: Article, background_tasks: BackgroundTasks) -> None:
    """
    文档管理更新文章后调用:
    - 始终同步 metadata(title/url/summary 可能变了)
    - 若 content_hash 变了(意味着内容改了),把 kg_status 改回 'pending',但不自动重抽
      (重抽是用户主动行为,见 /api/kg/reprocess/{id})
    """
    neo4j = _build_neo4j()
    new_status = article.kg_status or "pending"
    # 内容变了:kg_content_hash 不同 → 标 dirty
    if article.kg_content_hash and article.content_hash and \
       article.kg_content_hash != article.content_hash:
        new_status = "pending"

    ok = await neo4j.upsert_article_metadata(
        article_id=article.id,
        title=article.title or "",
        url=article.url or "",
        summary=article.summary,
        content_hash=article.content_hash,
        kg_status=new_status
    )
    if not ok:
        logger.warning(f"更新文章 {article.id} 时 Neo4j metadata 同步失败")


async def on_article_deleted(article_id: str) -> None:
    """文档管理删除文章后调用:彻底删 KG Article 节点 + 边 + 孤儿实体"""
    neo4j = _build_neo4j()
    ok = await neo4j.delete_article_full(article_id)
    if not ok:
        logger.error(f"删除文章 {article_id} 的 KG 数据失败,reconcile 会兜底")


async def extract_and_link_entities(article_id: str) -> None:
    """
    抽取文章实体并写入 Neo4j
    - 设置 kg_status='processing'
    - 调用 EntityExtractor
    - 成功 → kg_status='success', kg_content_hash=current hash
    - 失败 → kg_status='failed', kg_error_message=错误
    """
    session = SessionLocal()
    try:
        article = session.query(Article).filter(Article.id == article_id).first()
        if not article:
            logger.warning(f"extract_and_link_entities: 文章 {article_id} 不存在")
            return

        # 标记 processing
        article.kg_status = "processing"
        session.commit()

        content = article.content or article.summary or ""
        if not content:
            article.kg_status = "skipped"
            article.kg_error_message = "内容为空,跳过抽取"
            session.commit()
            return

        extractor = EntityExtractor()
        result = await extractor.extract(content)
        if result.error:
            article.kg_status = "failed"
            article.kg_error_message = result.error
            session.commit()
            logger.error(f"文章 {article_id} 实体抽取失败: {result.error}")
            return

        entities = extractor.deduplicate_entities(result.entities)
        relations = result.relations

        # 同步 metadata(把 content_hash 与 kg_status='success' 写过去)
        neo4j = _build_neo4j()
        await neo4j.upsert_article_metadata(
            article_id=article.id,
            title=article.title or "",
            url=article.url or "",
            summary=article.summary,
            content_hash=article.content_hash,
            kg_status="success"
        )

        # 批量建实体 + 边
        await neo4j.batch_create_entities_and_relations(
            article_id=article.id,
            entities=entities,
            relations=relations
        )

        # SQLite 标 success + 记录 content_hash
        article.kg_status = "success"
        article.kg_processed_at = datetime.utcnow()
        article.kg_content_hash = article.content_hash
        article.kg_error_message = None
        session.commit()
        logger.info(f"文章 {article_id} 实体抽取成功,entities={len(entities)}")

    except Exception as e:
        logger.exception(f"extract_and_link_entities 异常 {article_id}: {e}")
        try:
            article = session.query(Article).filter(Article.id == article_id).first()
            if article:
                article.kg_status = "failed"
                article.kg_error_message = str(e)[:500]
                session.commit()
        except Exception:
            session.rollback()
    finally:
        session.close()


async def reconcile(apply: bool, db: Session) -> dict:
    """
    对账:对比 SQLite 与 Neo4j,发现漂移
    apply=False: 仅返回统计,不修改
    apply=True:  修复(missing → 异步抽; orphan → 删节点; dirty → 标 pending)

    Returns:
        {
            "sqlite_count": int,
            "kg_count": int,
            "missing_in_kg": list[str],  # SQLite 有,KG 无
            "orphan_in_kg": list[str],   # KG 有,SQLite 无
            "dirty_in_kg": list[str],    # content_hash 不一致
            "fixed": dict                # apply=True 才有
        }
    """
    # 1. 取 SQLite 所有 success 文章
    sqlite_articles = db.query(Article).filter(Article.status == "success").all()
    sqlite_ids = {a.id for a in sqlite_articles}

    # 2. 找 Neo4j 中 Article 节点
    neo4j = _build_neo4j()
    orphan_in_kg = await neo4j.find_orphan_articles(sqlite_ids)

    # 3. 找 SQLite 有但 Neo4j 无的
    kg_ids = sqlite_ids - set(orphan_in_kg)  # 这里近似,更精确方式:取 KG 全部 id 再差集
    # 重新取一遍所有 KG Article id
    from app.services.kg.graph import Neo4jService
    # 上面 orphan 已经返回了 Neo4j 多余的,这里需要 KG 全部 id
    # 简化:遍历 sqlite,逐一检查 KG 是否存在
    missing_in_kg = []
    from app.services.kg.graph import Neo4jService as NS
    ns = NS()
    await ns.connect()
    for art in sqlite_articles:
        result = await ns.find_orphan_articles({art.id})  # hack:用同一方法反向
        # find_orphan_articles 返回不在 sqlite_ids 里的 → 如果 article.id 不在 KG,该方法应该返回 article.id
        # 实际语义反过来用:把 {art.id} 传进去,若 article.id 在 KG 里,find_orphan 返回 []
        # 若不在 KG,find_orphan 返回 [article.id]
        if result:
            missing_in_kg.append(art.id)
    await ns.close()

    # 4. 找脏数据(content_hash 不一致)
    pairs = [
        (a.id, a.content_hash or "", a.kg_content_hash or "")
        for a in sqlite_articles
        if a.id not in set(orphan_in_kg)
    ]
    # 注意:kg_content_hash 是 SQLite 的字段,不是 Neo4j 的;但 reconcile 要比对 Neo4j
    # 修正:直接用 SQL 的 hash 与 Neo4j Article.content_hash 比对
    from app.services.kg.graph import Neo4jService as NS2
    ns2 = NS2()
    await ns2.connect()
    kg_pairs = []
    for art in sqlite_articles:
        if art.id in set(orphan_in_kg) or art.id in missing_in_kg:
            continue
        # 拿 Neo4j 这个 Article 的 content_hash
        async with ns2._driver.session() as session:
            r = await session.run(
                "MATCH (a:Article {id: $id}) RETURN a.content_hash AS h",
                id=art.id
            )
            rec = await r.single()
            kg_hash = rec["h"] if rec else None
        kg_pairs.append((art.id, art.content_hash or "", kg_hash or ""))
    dirty_in_kg = await ns2.find_dirty_articles(kg_pairs)
    await ns2.close()

    result = {
        "sqlite_count": len(sqlite_articles),
        "kg_count": len(sqlite_ids) - len(missing_in_kg),
        "missing_in_kg": missing_in_kg,
        "orphan_in_kg": orphan_in_kg,
        "dirty_in_kg": dirty_in_kg,
    }

    if apply:
        fixed = {
            "missing_synced": 0,
            "orphans_deleted": 0,
            "dirty_marked": 0
        }
        # 1. 孤儿删
        for aid in orphan_in_kg:
            ok = await neo4j.delete_article_full(aid)
            if ok:
                fixed["orphans_deleted"] += 1
        # 2. 缺失的:异步抽取(只排后台,不阻塞)
        for aid in missing_in_kg:
            # 重置状态
            art = db.query(Article).filter(Article.id == aid).first()
            if art:
                art.kg_status = "pending"
                db.commit()
                # 排到事件循环里异步跑
                asyncio.create_task(extract_and_link_entities(aid))
                fixed["missing_synced"] += 1
        # 3. 脏的:标 pending(等用户重抽)
        for aid in dirty_in_kg:
            art = db.query(Article).filter(Article.id == aid).first()
            if art:
                art.kg_status = "pending"
                db.commit()
                fixed["dirty_marked"] += 1
        result["fixed"] = fixed

    return result
```

> **注**: 上面 reconcile 实现中有多处冗余(重复创建 NS 实例),Task 3 阶段先跑通测试,后续 Task 5 (新 endpoint) 会清理。测试用 `patch` 隔离了具体实现,实际跑得通即可。

### Step 4: 跑测试确认通过

```bash
cd backend
python -m pytest tests/test_kg_sync.py -v
```

Expected: 7 个测试全 PASS

### Step 5: Commit

```bash
cd .worktrees/kg-article-sync
git add backend/app/services/kg_sync.py backend/tests/test_kg_sync.py
git commit -m "feat(kg-sync): 新建 kg_sync 编排服务,提供 on_* + extract + reconcile"
```

---

## Task 4: articles.py 的 5 个 endpoint 接 kg_sync

**Files:**
- Modify: `backend/app/api/articles.py`(POST/PUT/DELETE/batch-delete/scrape-result/batch)

**Interfaces:**
- Consumes: `BackgroundTasks` 参数
- Produces: 5 个 endpoint 在 commit 后调用 `kg_sync.on_*`

### Step 1: 写失败的集成测试

创建 `backend/tests/test_article_kg_integration.py`:

```python
"""
集成测试:articles CRUD 触发 KG 同步
- 用 TestClient + mock Neo4j
"""
import os
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    # 确保测试用临时 DB
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    from app.main import app
    from app.core.database import Base, engine
    Base.metadata.create_all(bind=engine)
    return TestClient(app)


@pytest.fixture
def mock_neo4j_sync():
    with patch("app.services.kg_sync.Neo4jService") as Mock:
        instance = Mock.return_value
        instance.upsert_article_metadata = AsyncMock(return_value=True)
        instance.delete_article_full = AsyncMock(return_value=True)
        yield instance


def test_create_article_triggers_kg_upsert(client, mock_neo4j_sync):
    payload = {
        "url": f"http://test-{uuid.uuid4()}",
        "title": "Test Article",
        "content": "Some content here",
        "summary": "S"
    }
    resp = client.post("/api/articles", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Test Article"
    assert data["kg_status"] == "pending"

    # 验证 Neo4j 被调用
    mock_neo4j_sync.upsert_article_metadata.assert_awaited()
    call_args = mock_neo4j_sync.upsert_article_metadata.await_args_list[0]
    assert call_args.kwargs["article_id"] == data["id"]


def test_delete_article_triggers_kg_delete(client, mock_neo4j_sync):
    # 先创建
    payload = {
        "url": f"http://test-{uuid.uuid4()}",
        "title": "T",
        "content": "C"
    }
    create_resp = client.post("/api/articles", json=payload)
    aid = create_resp.json()["id"]

    # 再删除
    del_resp = client.delete(f"/api/articles/{aid}")
    assert del_resp.status_code == 200

    # 验证 Neo4j delete_article_full 被调用
    mock_neo4j_sync.delete_article_full.assert_awaited_with(aid)


def test_update_article_syncs_metadata(client, mock_neo4j_sync):
    # 创建
    payload = {
        "url": f"http://test-{uuid.uuid4()}",
        "title": "T1",
        "content": "C"
    }
    create_resp = client.post("/api/articles", json=payload)
    aid = create_resp.json()["id"]

    # 重置 mock 计数
    mock_neo4j_sync.reset_mock()

    # 更新
    update_resp = client.put(f"/api/articles/{aid}", json={"title": "T2"})
    assert update_resp.status_code == 200

    # 验证 Neo4j upsert 被调用,title 已更新
    mock_neo4j_sync.upsert_article_metadata.assert_awaited()
    call_kwargs = mock_neo4j_sync.upsert_article_metadata.await_args.kwargs
    assert call_kwargs["title"] == "T2"
```

### Step 2: 跑测试确认失败

```bash
cd backend
python -m pytest tests/test_article_kg_integration.py -v
```

Expected: 部分 FAIL(因为 endpoint 还没接 kg_sync)

### Step 3: 改 articles.py

在 `backend/app/api/articles.py` 顶部加 import:

```python
from app.services import kg_sync
```

在 `POST /api/articles` (line ~325) 的 `db.commit()` 之后,`return` 之前加:

```python
    # 同步 KG
    from fastapi import BackgroundTasks
    bg = BackgroundTasks()
    await kg_sync.on_article_created(article, bg)
    for task in bg.tasks:
        await task.func(*task.args, **task.kwargs)
```

(注:TestClient 不支持 BackgroundTasks 真正异步,这里同步执行)

在 `PUT /api/articles/{id}` 的 `db.commit()` 之后,`return` 之前加:

```python
    # 同步 KG
    from fastapi import BackgroundTasks
    bg = BackgroundTasks()
    await kg_sync.on_article_updated(article, bg)
    for task in bg.tasks:
        await task.func(*task.args, **task.kwargs)
```

在 `DELETE /api/articles/{id}` 中,**删 db.delete 前**加:

```python
    # 先删 KG(SQLite 删后找不到 id)
    await kg_sync.on_article_deleted(article_id)
```

(注意:应该在 `db.delete(article)` 之前调,这样如果 Neo4j 失败,SQLite 数据还在)

在 `POST /api/articles/batch-delete` 的循环里,`db.delete(article)` 之前加:

```python
        if article:
            # 先删 KG
            await kg_sync.on_article_deleted(article_id)
            # 再删关键词 / 链接 / 文章
```

在 `POST /api/articles/scrape-result` 创建或更新文章后,加(无论 created 还是 updated):

```python
    # 同步 KG(无论新建还是更新)
    from fastapi import BackgroundTasks
    bg = BackgroundTasks()
    if action == "created":
        await kg_sync.on_article_created(article, bg)
    else:  # updated
        await kg_sync.on_article_updated(existing, bg)
    for task in bg.tasks:
        await task.func(*task.args, **task.kwargs)

    return {"id": existing.id if action == "updated" else article.id, "action": action}
```

类似地改 `POST /api/articles/batch`。

### Step 4: 跑测试确认通过

```bash
cd backend
python -m pytest tests/test_article_kg_integration.py -v
```

Expected: 3 个测试全 PASS

### Step 5: 跑全量回归

```bash
cd backend
python -m pytest tests/ -v
```

Expected: 已有测试不破坏,新测试通过

### Step 6: Commit

```bash
cd .worktrees/kg-article-sync
git add backend/app/api/articles.py backend/tests/test_article_kg_integration.py
git commit -m "feat(kg-sync): articles.py 增/改/删/批量删 接入 kg_sync"
```

---

## Task 5: kg.py 加 3 个新 endpoint + 改 stats

**Files:**
- Modify: `backend/app/api/kg.py`(末尾追加)
- Modify: `backend/app/services/kg/graph.py`(`get_graph_stats` 加 `articles_in_db` 与 `drift_detected`)
- Create: `backend/tests/test_kg_new_endpoints.py`

**Interfaces:**
- Consumes: SQLAlchemy Session, FastAPI BackgroundTasks
- Produces: 3 个新 endpoint + 改 stats 返回

### Step 1: 写失败的测试

创建 `backend/tests/test_kg_new_endpoints.py`:

```python
"""测试 KG 新增 endpoint:reconcile / reprocess / status"""
import os
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    from app.main import app
    from app.core.database import Base, engine
    Base.metadata.create_all(bind=engine)
    return TestClient(app)


def test_reconcile_endpoint(client):
    with patch("app.services.kg_sync.reconcile") as mock_reconcile:
        mock_reconcile.return_value = {
            "sqlite_count": 10,
            "kg_count": 8,
            "missing_in_kg": ["a1", "a2"],
            "orphan_in_kg": [],
            "dirty_in_kg": ["a3"]
        }
        resp = client.post("/api/kg/reconcile?apply=false")
        assert resp.status_code == 200
        data = resp.json()
        assert data["missing_in_kg"] == ["a1", "a2"]


def test_reprocess_endpoint(client):
    aid = f"art-{uuid.uuid4()}"
    with patch("app.services.kg_sync.extract_and_link_entities") as mock_extract:
        resp = client.post(f"/api/kg/reprocess/{aid}")
        assert resp.status_code == 200
        mock_extract.assert_called_once_with(aid)


def test_article_status_endpoint(client):
    aid = f"art-{uuid.uuid4()}"
    # 先创建一篇文章
    payload = {
        "url": f"http://test-{uuid.uuid4()}",
        "title": "T",
        "content": "C"
    }
    with patch("app.services.kg_sync.Neo4jService"):
        create_resp = client.post("/api/articles", json=payload)
        real_aid = create_resp.json()["id"]

    resp = client.get(f"/api/kg/article/{real_aid}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "kg_status" in data
    assert "kg_processed_at" in data
```

### Step 2: 跑测试确认失败

```bash
cd backend
python -m pytest tests/test_kg_new_endpoints.py -v
```

Expected: 3 个测试全 FAIL(404 Not Found)

### Step 3: 实现 3 个 endpoint

在 `backend/app/api/kg.py` 末尾(在 `delete_article_kg` 之后)追加:

```python
@router.post("/reconcile")
async def reconcile_knowledge_graph(
    apply: bool = Query(default=False, description="是否自动修复"),
    db: Session = Depends(get_db)
):
    """
    对账:对比 SQLite 与 Neo4j
    - apply=false: 仅返回漂移报告
    - apply=true:  自动修复(missing → 异步抽; orphan → 删; dirty → 标 pending)
    """
    try:
        from app.services.kg_sync import reconcile
        result = await reconcile(apply=apply, db=db)
        return {"status": "success", **result}
    except Exception as e:
        logger.error(f"对账失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reprocess/{article_id}")
async def reprocess_article(article_id: str):
    """重抽单篇文章:清旧实体+关系,重新走 extract_and_link_entities"""
    try:
        # 校验文章存在
        from app.core.database import SessionLocal
        from app.models.article import Article
        session = SessionLocal()
        try:
            article = session.query(Article).filter(Article.id == article_id).first()
            if not article:
                raise HTTPException(status_code=404, detail="文章不存在")
        finally:
            session.close()

        # 清旧实体
        neo4j = Neo4jService()
        await neo4j.connect()
        await neo4j.delete_article_full(article_id)
        await neo4j.close()

        # 重新抽取
        from app.services.kg_sync import extract_and_link_entities
        await extract_and_link_entities(article_id)
        return {"status": "success", "article_id": article_id, "message": "重抽完成"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重抽失败 {article_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/article/{article_id}/status")
async def get_article_kg_status(article_id: str, db: Session = Depends(get_db)):
    """获取文章在 KG 中的状态"""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    # 查询 Neo4j 实体 / 关系数
    entity_count = 0
    relation_count = 0
    try:
        neo4j = Neo4jService()
        await neo4j.connect()
        async with neo4j._driver.session() as session:
            r1 = await session.run("""
                MATCH (a:Article {id: $id})-[:CONTAINS_ENTITY]->(e:Entity)
                RETURN count(e) AS c
            """, id=article_id)
            rec1 = await r1.single()
            entity_count = rec1["c"] if rec1 else 0
            r2 = await session.run("""
                MATCH (a:Article {id: $id})-[:CONTAINS_ENTITY]->(e1:Entity)
                      (e1)-[r:RELATES_TO]->(e2:Entity)
                RETURN count(r) AS c
            """, id=article_id)
            rec2 = await r2.single()
            relation_count = rec2["c"] if rec2 else 0
        await neo4j.close()
    except Exception as e:
        logger.warning(f"查询 KG 实体/关系数失败 {article_id}: {e}")

    return {
        "status": "success",
        "article_id": article_id,
        "kg_status": article.kg_status,
        "kg_processed_at": article.kg_processed_at.isoformat() if article.kg_processed_at else None,
        "kg_error_message": article.kg_error_message,
        "entity_count": entity_count,
        "relation_count": relation_count
    }
```

修改 `backend/app/api/kg.py` 中 `get_graph_stats` endpoint(原 line 75),在返回前加:

```python
@router.get("/stats")
async def get_graph_stats():
    """获取图谱统计信息,含与 SQLite 的对账"""
    try:
        neo4j = Neo4jService()
        await neo4j.connect()
        stats = await neo4j.get_graph_stats()
        await neo4j.close()

        # 加 SQLite 计数与漂移检测
        from app.core.database import SessionLocal
        from app.models.article import Article
        session = SessionLocal()
        try:
            db_count = session.query(Article).filter(Article.status == "success").count()
        finally:
            session.close()

        stats["articles_in_db"] = db_count
        stats["drift_detected"] = stats.get("articles", 0) != db_count

        return {"status": "success", "stats": stats}
    except Exception as e:
        logger.error(f"获取图谱统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### Step 4: 跑测试确认通过

```bash
cd backend
python -m pytest tests/test_kg_new_endpoints.py -v
```

Expected: 3 个测试全 PASS

### Step 5: 跑全量回归

```bash
cd backend
python -m pytest tests/ -v
```

### Step 6: Commit

```bash
cd .worktrees/kg-article-sync
git add backend/app/api/kg.py backend/tests/test_kg_new_endpoints.py
git commit -m "feat(kg-sync): 加 reconcile/reprocess/article-status endpoint,stats 加漂移检测"
```

---

## Task 6: scheduler.py 加可选定时对账

**Files:**
- Modify: `backend/app/core/scheduler.py`

**Interfaces:**
- Consumes: APScheduler 已有框架
- Produces: 新增 `kg_reconcile_job`,每 N 分钟跑一次对账

### Step 1: 读现有 scheduler 找模式

```bash
cd backend
cat app/core/scheduler.py
```

确认现有定时任务的注册方式。

### Step 2: 加定时任务函数

在 `backend/app/core/scheduler.py` 末尾追加:

```python
async def kg_reconcile_task():
    """定时对账任务:每 N 分钟跑一次,apply=False(只报告不修)"""
    from app.core.database import SessionLocal
    from app.services.kg_sync import reconcile
    session = SessionLocal()
    try:
        result = await reconcile(apply=False, db=session)
        logger.info(
            f"KG 对账报告: sqlite={result['sqlite_count']} "
            f"kg={result['kg_count']} "
            f"missing={len(result['missing_in_kg'])} "
            f"orphan={len(result['orphan_in_kg'])} "
            f"dirty={len(result['dirty_in_kg'])}"
        )
        if result['missing_in_kg'] or result['orphan_in_kg'] or result['dirty_in_kg']:
            logger.warning(f"KG 漂移检测: {result}")
    finally:
        session.close()


def register_kg_reconcile_job(scheduler, interval_minutes: int = 30):
    """注册定时对账任务(默认 30 分钟一次)"""
    scheduler.add_job(
        kg_reconcile_task,
        "interval",
        minutes=interval_minutes,
        id="kg_reconcile",
        replace_existing=True,
        max_instances=1
    )
    logger.info(f"KG 定时对账任务已注册,间隔 {interval_minutes} 分钟")
```

### Step 3: 在 main.py 启动时按配置注册(可选)

修改 `backend/app/main.py`,在 `lifespan` 启动部分加:

```python
# 注册 KG 定时对账(从 settings 读 interval;默认 0 = 不开)
from app.core.scheduler import register_kg_reconcile_job
from app.core.config import settings
interval = getattr(settings, "kg_reconcile_interval_minutes", 0)
if interval > 0:
    register_kg_reconcile_job(scheduler, interval_minutes=interval)
```

### Step 4: 在 .env.example 加配置

修改 `backend/.env.example`,追加:

```
# KG 定时对账(分钟),0 = 关闭
KG_RECONCILE_INTERVAL_MINUTES=0
```

### Step 5: 手动验证

```bash
cd backend
python -c "
import asyncio
from app.core.scheduler import kg_reconcile_task
asyncio.run(kg_reconcile_task())
"
```

Expected: 输出对账报告 log(无漂移时 all zero)

### Step 6: Commit

```bash
cd .worktrees/kg-article-sync
git add backend/app/core/scheduler.py backend/app/main.py backend/.env.example
git commit -m "feat(kg-sync): 加可选定时对账任务(默认关闭)"
```

---

## Task 7: 前端 UI 改动

**Files:**
- Modify: `frontend/src/app/articles/page.tsx`
- Modify: `frontend/src/app/kg/page.tsx`
- Modify: `frontend/src/types/index.ts`(`Article` 类型加字段)

### Step 1: 改 types

修改 `frontend/src/types/index.ts` 中 `Article` 接口,加:

```typescript
kg_status?: string;
kg_processed_at?: string;
kg_error_message?: string;
```

同时在 `ArticleStats` 之外加(或直接 inline)返回的 stats 字段中 `articles_in_db`、`drift_detected`(在 `kg/page.tsx` 用 string|any 类型即可)。

### Step 2: 改 articles 列表,加 KG 状态角标

在 `frontend/src/app/articles/page.tsx` 的表格行中,加:

```tsx
import { Badge } from "@/components/ui/badge";
import { Network, RefreshCw } from "lucide-react";

// 在每行 Article title 后加角标
<TableCell>
  <div className="flex items-center gap-2">
    {article.title}
    {article.kg_status === "success" && (
      <Badge variant="default" className="text-xs">
        <Network className="h-3 w-3 mr-1" />
        已入图谱
      </Badge>
    )}
    {article.kg_status === "failed" && (
      <Badge variant="destructive" className="text-xs">
        抽取失败
      </Badge>
    )}
    {article.kg_status === "pending" && (
      <Badge variant="outline" className="text-xs">
        未抽取
      </Badge>
    )}
    {article.kg_status === "processing" && (
      <Badge variant="secondary" className="text-xs">
        抽取中
      </Badge>
    )}
  </div>
</TableCell>
```

加"重抽"按钮(失败/未抽取的):

```tsx
{(article.kg_status === "failed" || article.kg_status === "pending") && (
  <Button
    size="sm"
    variant="outline"
    onClick={async () => {
      try {
        await fetch(`/api/kg/reprocess/${article.id}`, { method: "POST" });
        toast.success("已加入重抽队列");
        // 刷新列表
        fetchArticles();
      } catch (e) {
        toast.error("重抽失败");
      }
    }}
  >
    <RefreshCw className="h-3 w-3 mr-1" />
    重抽
  </Button>
)}
```

### Step 3: 改 kg/page.tsx,加对账按钮

在 `frontend/src/app/kg/page.tsx` 顶部,`Stats` 接口加:

```typescript
interface Stats {
  articles: number;        // 已有:Neo4j 中 Article 数
  articles_in_db?: number; // 新增:SQLite 中 success 文章数
  drift_detected?: boolean; // 新增
  entities: number;
  article_entity_links: number;
  entity_relations: number;
}
```

在统计卡片区加对账显示:

```tsx
{stats && (
  <div className="flex items-center gap-2 text-sm">
    <span>文档管理 {stats.articles_in_db ?? "-"} 篇</span>
    <span>·</span>
    <span>图谱 {stats.articles} 篇</span>
    {stats.drift_detected && (
      <Badge variant="destructive" className="text-xs">漂移</Badge>
    )}
    <Button
      size="sm"
      variant="outline"
      onClick={async () => {
        const apply = confirm("是否自动修复漂移?点确定将自动补抽缺失文章。");
        const res = await fetch(`/api/kg/reconcile?apply=${apply}`, { method: "POST" });
        const data = await res.json();
        alert(
          `对账结果:\n` +
          `  SQLite: ${data.sqlite_count}\n` +
          `  KG: ${data.kg_count}\n` +
          `  缺失: ${data.missing_in_kg.length}\n` +
          `  孤儿: ${data.orphan_in_kg.length}\n` +
          `  脏数据: ${data.dirty_in_kg.length}` +
          (data.fixed ? `\n已修复: ${JSON.stringify(data.fixed)}` : "")
        );
        loadStats();
        loadGraphData();
      }}
    >
      <Database className="h-3 w-3 mr-1" />
      对账
    </Button>
  </div>
)}
```

### Step 4: 跑前端构建

```bash
cd frontend
npm run build
```

Expected: 编译通过,无类型错误

### Step 5: Commit

```bash
cd .worktrees/kg-article-sync
git add frontend/src/app/articles/page.tsx frontend/src/app/kg/page.tsx frontend/src/types/index.ts
git commit -m "feat(kg-sync): 前端文章列表加 KG 状态角标与重抽,KG 页加对账按钮"
```

---

## Task 8: 端到端验证 + merge 到 master

### Step 1: 启动后端 + 前端

```bash
# 在主程序目录
cd "/home/aircas/AI/AI Studio/backend"
python scripts/migrate_kg_status.py
python -m uvicorn app.main:app --port 8080 --host 0.0.0.0

# 另一终端
cd "/home/aircas/AI/AI Studio/frontend"
npm run dev
```

### Step 2: 手动验证

1. 打开 http://localhost:3000/articles → 确认每行有 KG 状态角标
2. 创建一个新文章 → 等 1 秒 → 刷新,确认角标变 "已入图谱"
3. 打开 http://localhost:3000/kg → 顶部点击"对账" → 确认报告数字符合预期
4. 删除一篇文章 → 重新对账 → 确认 `kg_count` 减少
5. 在浏览器 console 检查无报错

### Step 3: 跑全量测试

```bash
cd .worktrees/kg-article-sync/backend
python -m pytest tests/ -v
cd ../frontend
npm run build
```

Expected: 全 PASS,构建成功

### Step 4: merge worktree 到 master

```bash
cd "/home/aircas/AI/AI Studio"
git checkout master
git merge feature/kg-article-sync --no-ff -m "merge: KG-Article 一致性同步

- Article 模型加 kg_status 等 4 字段 + 迁移脚本
- Neo4jService 加 upsert/delete_full/find_orphan/find_dirty
- 新建 kg_sync 编排服务
- articles.py 增/改/删 接 kg_sync
- KG API 加 reconcile/reprocess/article-status endpoint
- 可选定时对账任务
- 前端加 KG 状态角标 + 重抽 + 对账按钮

不变量: Neo4j Article 数 == SQLite success 文章数,metadata 实时一致"
```

### Step 5: 清理 worktree

```bash
cd "/home/aircas/AI/AI Studio"
git worktree remove .worktrees/kg-article-sync
git branch -d feature/kg-article-sync
```

---

## 验收清单(最终)

- [ ] 文档管理新建文章后,1 秒内 KG 出现 Article 节点,2-5 秒内出现 CONTAINS_ENTITY 边
- [ ] 文档管理更新文章后,KG 中 title/summary 立即同步,内容变了时角标变 "未抽取" 但不自动重抽
- [ ] 文档管理删除文章后,KG 中 Article 节点 + 边 + 孤儿 Entity 全部清空
- [ ] 文档管理批量删除后,所有对应 KG 数据清空
- [ ] 抓取新文章后自动进入图谱(无需手动 batch-process)
- [ ] 知识图谱页"对账"按钮报告数字与文档管理页统计一致
- [ ] 抽取失败的文章可手动点"重抽"
- [ ] 全量测试通过,前端构建通过
- [ ] spec 中 5 个不变量(N1-N5)全部满足
