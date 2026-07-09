# KG-QA-in-Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有对话页集成知识图谱问答,带 Mini D3 子图、原文出处 Popover 与文章页高亮跳转。

**Architecture:**
- 后端:新增 `qa.py` 服务 + `prompts.py` 模板 + `POST /api/kg/qa/answer` 与 `GET /api/kg/entity-context/{name}` 端点;`EntityNode` 扩展 `source_articles` 字段并在抽取时回写
- 前端:ChatPage 加 `kgEnhanced` 开关,启用时改走新接口;回答消息内嵌 `MiniGraph` 与 `EntitySourcePopover`;文章页支持 `?highlight=X` URL query + `HighlightOverlay` 浮窗

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async、Neo4j 5.x async driver、Next.js 16 + React 19、Zustand、D3 7.x、TypeScript 5.x

---

## Global Constraints

- **Python**:3.11+,async/await 全程使用
- **后端依赖**:`neo4j>=5.20`、`fastapi>=0.115`、`pydantic>=2.7`、`sqlalchemy>=2.0`
- **前端依赖**:`next>=16`、`react>=19`、`zustand>=4.5`、`d3>=7.9`、`lucide-react`
- **Neo4j**:`bolt://localhost:7687`,env `NEO4J_PASSWORD` 默认 `password`
- **命名规范**:后端 snake_case,前端 camelCase
- **API 前缀**:后端 `/api/kg/*`,前端 catch-all proxy `/api/kg/[...path]`
- **测试**:后端 pytest + httpx
- **中文 commit 风格**:动词 + 模块,如 `feat(kg): ...`
- **降级原则**:任何失败都优先返回可用信息,不抛 500 给前端
- **不破坏**:原 `/api/chat/stream` 端点、原 `chat-store` 核心结构

---

## File Structure (M1 + M2)

**Backend 新增:**
- `backend/app/services/kg/prompts.py`
- `backend/app/services/kg/qa.py`
- `backend/scripts/kg_health_check.py`
- `backend/scripts/kg_backfill_sources.py`
- `backend/tests/services/kg/test_qa.py`
- `backend/tests/services/kg/test_prompts.py`
- `backend/tests/services/kg/test_graph_source_articles.py`
- `backend/tests/services/kg/test_extractor_source.py`
- `backend/tests/scripts/test_kg_health_check.py`
- `backend/tests/api/test_kg_qa.py`

**Backend 修改:**
- `backend/app/services/kg/graph.py`
- `backend/app/services/kg/extractor.py`
- `backend/app/services/kg/kg_sync.py`
- `backend/app/api/kg.py`

**Frontend 新增:**
- `frontend/src/components/kg/MiniGraph.tsx`
- `frontend/src/components/kg/EntitySourcePopover.tsx`
- `frontend/src/components/articles/HighlightOverlay.tsx`
- `frontend/src/lib/api-kg.ts`

**Frontend 修改:**
- `frontend/src/stores/chat-store.ts`
- `frontend/src/app/page.tsx`
- `frontend/src/types/index.ts`
- `frontend/src/app/articles/page.tsx`
- `frontend/src/app/globals.css` (高亮样式)
- `frontend/src/app/kg/page.tsx`

---

# Milestone 1 — 数据评估 + 对话页 RAG

## Task 1: 数据评估脚本

**Files:**
- Create: `backend/scripts/kg_health_check.py`
- Create: `backend/tests/scripts/test_kg_health_check.py`

- [ ] **Step 1: 写测试**

```python
# backend/tests/scripts/test_kg_health_check.py
import json
from pathlib import Path
from scripts.kg_health_check import analyze, write_report

def test_analyze_returns_required_keys():
    stats = {
        "total_nodes": 100, "total_relationships": 200,
        "entities_by_type": {"PERSON": 50, "TECHNOLOGY": 30},
        "entities_by_subtype": {"SCIENTIST": 10}
    }
    result = analyze(stats, articles_in_kg=10)
    assert "summary" in result
    assert "entity_type_distribution" in result
    assert "recommendations" in result
    assert result["summary"]["total_nodes"] == 100

def test_write_report_creates_file(tmp_path):
    report = {"summary": {"total_nodes": 1}}
    out = tmp_path / "report.json"
    write_report(report, out)
    assert out.exists()
    assert json.loads(out.read_text())["summary"]["total_nodes"] == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/scripts/test_kg_health_check.py -v`
Expected: `ModuleNotFoundError: No module named 'scripts'`

- [ ] **Step 3: 实现脚本**

```python
# backend/scripts/kg_health_check.py
"""知识图谱数据健康评估脚本"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.kg import Neo4jService  # noqa: E402


def analyze(stats: Dict[str, Any], articles_in_kg: int) -> Dict[str, Any]:
    coverage = 0.0
    recs: List[str] = []
    if stats.get("total_relationships", 0) < stats.get("total_nodes", 0):
        recs.append("关系数少于节点数,存在孤立节点,建议补抽")
    if not stats.get("entities_by_subtype"):
        recs.append("未发现 subtype 细分,建议检查抽取 prompt 是否生效")
    return {
        "summary": {
            "total_nodes": stats.get("total_nodes", 0),
            "total_relationships": stats.get("total_relationships", 0),
            "articles_in_kg": articles_in_kg,
            "source_articles_coverage": coverage,
        },
        "entity_type_distribution": stats.get("entities_by_type", {}),
        "subtype_distribution": stats.get("entities_by_subtype", {}),
        "recommendations": recs,
    }


def write_report(report: Dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


async def main() -> None:
    neo4j = Neo4jService()
    await neo4j.connect()
    try:
        stats = await neo4j.get_graph_stats()
        async with neo4j._driver.session() as session:
            r = await session.run("MATCH (a:Article) RETURN count(a) AS c")
            articles_count = (await r.single())["c"]
            r2 = await session.run(
                "MATCH (e:Entity) WHERE e.source_articles IS NOT NULL AND size(e.source_articles) > 0 RETURN count(e) AS c"
            )
            covered = (await r2.single())["c"]
        coverage = covered / stats["total_nodes"] if stats.get("total_nodes") else 0.0
        report = analyze(stats, articles_in_kg=articles_count)
        report["summary"]["source_articles_coverage"] = round(coverage, 4)
    finally:
        await neo4j.close()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = Path(f"reports/kg_health_{ts}.json")
    write_report(report, out_path)
    print(f"✓ 报告已生成: {out_path}")
    print(f"  总节点: {report['summary']['total_nodes']}")
    print(f"  关系数: {report['summary']['total_relationships']}")
    print(f"  实体-文章覆盖率: {report['summary']['source_articles_coverage'] * 100:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: 跑测试通过**

Run: `cd backend && python -m pytest tests/scripts/test_kg_health_check.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 真实跑一次**

Run: `cd backend && python scripts/kg_health_check.py`
Expected: 输出 `reports/kg_health_<ts>.json` + 摘要

- [ ] **Step 6: 提交**

```bash
cd /home/aircas/AI/AI\ Studio
git add backend/scripts/kg_health_check.py backend/tests/scripts/
git commit -m "feat(kg): 数据健康评估脚本"
```

---

## Task 2: EntityNode.source_articles + 累积写入

**Files:**
- Modify: `backend/app/services/kg/graph.py`
- Create: `backend/tests/services/kg/test_graph_source_articles.py`

- [ ] **Step 1: 写测试**

```python
# backend/tests/services/kg/test_graph_source_articles.py
import pytest
from app.services.kg.graph import EntityNode, Neo4jService

@pytest.mark.asyncio
async def test_create_entity_node_merges_source_articles():
    neo4j = Neo4jService()
    await neo4j.connect()
    try:
        name = "__test_entity_src_articles__"
        async with neo4j._driver.session() as s:
            await s.run("MATCH (e:Entity {name:$n}) DETACH DELETE e", n=name)
        await neo4j.create_entity_node(name=name, entity_type="PERSON", source_articles=["art-1"])
        await neo4j.create_entity_node(name=name, entity_type="PERSON", source_articles=["art-2"])
        async with neo4j._driver.session() as s:
            r = await s.run("MATCH (e:Entity {name:$n}) RETURN e.source_articles AS sa", n=name)
            row = await r.single()
            sa = sorted(row["sa"] or [])
            assert "art-1" in sa and "art-2" in sa
    finally:
        await neo4j.close()

@pytest.mark.asyncio
async def test_create_entity_node_without_source_articles_ok():
    neo4j = Neo4jService()
    await neo4j.connect()
    try:
        assert await neo4j.create_entity_node(name="__test_no_src__", entity_type="PERSON") is True
        async with neo4j._driver.session() as s:
            await s.run("MATCH (e:Entity {name:$n}) DETACH DELETE e", n="__test_no_src__")
    finally:
        await neo4j.close()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/services/kg/test_graph_source_articles.py -v`
Expected: FAIL (TypeError: unexpected keyword argument 'source_articles')

- [ ] **Step 3: 修改 EntityNode**

```python
# backend/app/services/kg/graph.py:11-20
@dataclass
class EntityNode:
    """实体节点"""
    name: str
    entity_type: str
    description: Optional[str] = None
    subtype: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    source_articles: Optional[List[str]] = None
```

- [ ] **Step 4: 修改 create_entity_node**

```python
# backend/app/services/kg/graph.py:136-180
async def create_entity_node(
    self,
    name: str,
    entity_type: str,
    description: Optional[str] = None,
    subtype: Optional[str] = None,
    source_articles: Optional[List[str]] = None,
) -> bool:
    if not self._driver:
        await self.connect()
    new_articles = source_articles or []

    async with self._driver.session() as session:
        if new_articles:
            query = """
            MERGE (e:Entity {name: $name})
            SET e.entity_type = $entity_type,
                e.description = $description,
                e.subtype = $subtype,
                e.source_articles = REDUCE(acc = coalesce(e.source_articles, []), item IN $new_articles |
                    CASE WHEN item IN acc THEN acc ELSE acc + item END),
                e.updated_at = datetime()
            RETURN e
            """
            await session.run(query, name=name, entity_type=entity_type,
                              description=description, subtype=subtype, new_articles=new_articles)
        else:
            query = """
            MERGE (e:Entity {name: $name})
            SET e.entity_type = $entity_type,
                e.description = $description,
                e.subtype = $subtype,
                e.updated_at = datetime()
            RETURN e
            """
            await session.run(query, name=name, entity_type=entity_type,
                              description=description, subtype=subtype)
    return True
```

- [ ] **Step 5: 同步 batch_create_entities_and_relations**

定位 `batch_create_entities_and_relations`,在创建 entity node 处传入 `source_articles`:

```python
await self.create_entity_node(
    name=ent.name,
    entity_type=ent.entity_type,
    description=ent.description,
    subtype=ent.subtype,
    source_articles=ent.source_articles,
)
```

- [ ] **Step 6: 跑测试通过**

Run: `cd backend && python -m pytest tests/services/kg/test_graph_source_articles.py -v`
Expected: PASS (2 passed)

- [ ] **Step 7: 提交**

```bash
cd /home/aircas/AI/AI\ Studio
git add backend/app/services/kg/graph.py backend/tests/services/kg/test_graph_source_articles.py
git commit -m "feat(kg): EntityNode 支持 source_articles 累积"
```

---

## Task 3: extractor.py 抽取时记录 source_articles

**Files:**
- Modify: `backend/app/services/kg/extractor.py`
- Modify: `backend/app/services/kg/kg_sync.py`
- Create: `backend/tests/services/kg/test_extractor_source.py`

- [ ] **Step 1: 写测试**

```python
# backend/tests/services/kg/test_extractor_source.py
import pytest
from app.services.kg.extractor import EntityExtractor

@pytest.mark.asyncio
async def test_extract_populates_source_articles(monkeypatch):
    extractor = EntityExtractor()
    async def mock_llm(prompt, **kwargs):
        return '{"entities": [{"name": "X", "type": "PERSON", "subtype": "SCIENTIST", "description": "x"}], "relationships": []}'
    monkeypatch.setattr(extractor, "_call_llm", mock_llm)
    nodes, rels = await extractor.extract(text="Some text about X.", article_id="art-abc-123")
    assert len(nodes) == 1
    assert nodes[0].source_articles == ["art-abc-123"]

@pytest.mark.asyncio
async def test_extract_without_article_id_keeps_none(monkeypatch):
    async def mock_llm(prompt, **kwargs):
        return '{"entities": [{"name": "X", "type": "PERSON"}], "relationships": []}'
    extractor = EntityExtractor()
    monkeypatch.setattr(extractor, "_call_llm", mock_llm)
    nodes, _ = await extractor.extract(text="X is here.")
    assert nodes[0].source_articles is None
```

- [ ] **Step 2: 跑测试失败**

Run: `cd backend && python -m pytest tests/services/kg/test_extractor_source.py -v`
Expected: FAIL

- [ ] **Step 3: 修改 extract 签名**

```python
# backend/app/services/kg/extractor.py
async def extract(
    self,
    text: str,
    article_id: Optional[str] = None,
    **kwargs,
) -> Tuple[List[EntityNode], List[Relationship]]:
    # 内部构造 EntityNode:
    entities.append(EntityNode(
        name=e["name"].strip(),
        entity_type=entity_type,
        description=e.get("description", "").strip(),
        subtype=subtype,
        source_articles=[article_id] if article_id else None,
    ))
```

- [ ] **Step 4: 跑测试通过**

Run: `cd backend && python -m pytest tests/services/kg/test_extractor_source.py -v`
Expected: PASS

- [ ] **Step 5: 调用方传 article_id**

```bash
cd backend && grep -rn "\.extract(" app/services/kg_sync.py
```

在 `kg_sync.py` 中改为:

```python
await extractor.extract(text=article.content, article_id=str(article.id))
```

- [ ] **Step 6: 提交**

```bash
cd /home/aircas/AI/AI\ Studio
git add backend/app/services/kg/extractor.py backend/app/services/kg/kg_sync.py backend/tests/services/kg/test_extractor_source.py
git commit -m "feat(kg): 抽取时记录 source_articles"
```

---

## Task 4: prompts.py 模板

**Files:**
- Create: `backend/app/services/kg/prompts.py`
- Create: `backend/tests/services/kg/test_prompts.py`

- [ ] **Step 1: 写测试**

```python
# backend/tests/services/kg/test_prompts.py
from app.services.kg.prompts import (
    EXTRACT_ENTITIES_FROM_QUESTION_PROMPT,
    ANSWER_WITH_GRAPH_PROMPT,
    SUBTYPE_GUIDE,
)

def test_extract_prompt_has_placeholders():
    assert "{question}" in EXTRACT_ENTITIES_FROM_QUESTION_PROMPT
    assert "{subtype_guide}" in EXTRACT_ENTITIES_FROM_QUESTION_PROMPT

def test_answer_prompt_has_placeholders():
    assert "{context}" in ANSWER_WITH_GRAPH_PROMPT
    assert "{question}" in ANSWER_WITH_GRAPH_PROMPT

def test_subtype_guide_has_seven_categories():
    for k in ("PERSON", "ORGANIZATION", "LOCATION", "TECHNOLOGY", "EVENT", "CONCEPT", "DATE"):
        assert k in SUBTYPE_GUIDE
```

- [ ] **Step 2: 跑测试失败**

Run: `cd backend && python -m pytest tests/services/kg/test_prompts.py -v`
Expected: FAIL

- [ ] **Step 3: 创建 prompts.py**

```python
# backend/app/services/kg/prompts.py
"""知识图谱问答使用的 prompt 模板"""

SUBTYPE_GUIDE: dict = {
    "PERSON":      "SCIENTIST|ENGINEER|ACADEMIC|POLITICIAN|ENTREPRENEUR|WRITER|ARTIST|HISTORICAL|OTHER",
    "ORGANIZATION": "COMPANY|RESEARCH_INST|UNIVERSITY|GOVERNMENT|INTERNATIONAL|NGO|OTHER",
    "LOCATION":    "CITY|COUNTRY|REGION|BUILDING|ASTRONOMICAL|NATURAL|OTHER",
    "TECHNOLOGY":  "AI_MODEL|ALGORITHM|PRODUCT|LANGUAGE|FRAMEWORK|TOOL|MATERIAL|BIOTECH|ENERGY|DEVICE|OTHER",
    "EVENT":       "DISCOVERY|CONFERENCE|PUBLICATION|AWARD|AGREEMENT|DISASTER|CONFLICT|OTHER",
    "CONCEPT":     "THEORY|LAW|METHOD|MODEL|SYSTEM|IDEA|DISCIPLINE|FIELD|OTHER",
    "DATE":        "YEAR|MONTH|DAY|ERA|PERIOD|OTHER",
}


EXTRACT_ENTITIES_FROM_QUESTION_PROMPT = """你是实体抽取助手。从用户问题中识别关键实体。

要求:
- name: 实体原文(不要翻译、不要简化)
- type: 必须是以下之一: PERSON | ORGANIZATION | LOCATION | TECHNOLOGY | EVENT | CONCEPT | DATE
- subtype: 该 type 下的细分,候选如下:
{subtype_guide}
- 只输出 JSON 数组,无其他文字

示例问题: "OpenAI 是什么时候成立的?Sam Altman 之前在哪家公司?"
示例输出: [
  {{"name": "OpenAI", "type": "ORGANIZATION", "subtype": "COMPANY"}},
  {{"name": "Sam Altman", "type": "PERSON", "subtype": "ENTREPRENEUR"}}
]

用户问题: {question}
JSON 数组:
"""


ANSWER_WITH_GRAPH_PROMPT = """你是基于知识图谱的问答助手。严格依据下方"图谱事实"回答,不要编造。
如信息不足,直接说"图谱中暂未收录"。

回答要求:
- 用 [n] 标注引用,顺序对应下方事实
- 不要超出图谱事实范围
- 简洁,2-4 句

图谱事实:
{context}

用户问题: {question}
回答:
"""
```

- [ ] **Step 4: 跑测试通过**

Run: `cd backend && python -m pytest tests/services/kg/test_prompts.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 提交**

```bash
cd /home/aircas/AI/AI\ Studio
git add backend/app/services/kg/prompts.py backend/tests/services/kg/test_prompts.py
git commit -m "feat(kg): 问答 prompt 模板"
```

---

## Task 5: qa.py — 实体抽取与子图查询

**Files:**
- Create: `backend/app/services/kg/qa.py`
- Create: `backend/tests/services/kg/test_qa.py`

- [ ] **Step 1: 写测试**

```python
# backend/tests/services/kg/test_qa.py
import pytest
from app.services.kg.qa import extract_entities_from_question

@pytest.mark.asyncio
async def test_extract_entities_parses_json():
    async def mock_llm(prompt, **kwargs):
        return '[{"name": "OpenAI", "type": "ORGANIZATION", "subtype": "COMPANY"}]'
    result = await extract_entities_from_question(
        "OpenAI 啥时候成立?", model_id="x", llm_caller=mock_llm
    )
    assert len(result) == 1
    assert result[0]["name"] == "OpenAI"
    assert result[0]["type"] == "ORGANIZATION"

@pytest.mark.asyncio
async def test_extract_entities_empty_on_invalid_json():
    async def mock_llm(prompt, **kwargs):
        return "not json"
    result = await extract_entities_from_question("?", model_id="x", llm_caller=mock_llm)
    assert result == []

@pytest.mark.asyncio
async def test_extract_entities_handles_failure():
    async def mock_llm(prompt, **kwargs):
        raise RuntimeError("boom")
    result = await extract_entities_from_question("?", model_id="x", llm_caller=mock_llm)
    assert result == []
```

- [ ] **Step 2: 跑测试失败**

Run: `cd backend && python -m pytest tests/services/kg/test_qa.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 qa.py (前两个函数)**

```python
# backend/app/services/kg/qa.py
"""知识图谱问答服务"""
import json
import logging
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional

from app.services.kg import Neo4jService
from app.services.kg.prompts import (
    EXTRACT_ENTITIES_FROM_QUESTION_PROMPT,
    SUBTYPE_GUIDE,
)

logger = logging.getLogger("ai-studio")

LlmCaller = Callable[..., Awaitable[str]]


async def _default_llm_caller(prompt: str, model_id: str, **kwargs) -> str:
    from app.services.llm_service import chat_complete
    return await chat_complete(prompt=prompt, model_id=model_id, temperature=0.0, **kwargs)


def _parse_json_array(text: str) -> List[Dict[str, Any]]:
    m = re.search(r"\[\s*[\s\S]*?\]\s*$", text.strip())
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
        return [d for d in data if isinstance(d, dict) and d.get("name")]
    except (json.JSONDecodeError, ValueError):
        logger.warning(f"qa: 无法解析 LLM 输出: {text[:200]}")
        return []


async def extract_entities_from_question(
    question: str,
    model_id: str,
    llm_caller: Optional[LlmCaller] = None,
) -> List[Dict[str, Any]]:
    caller = llm_caller or _default_llm_caller
    subtype_lines = "\n".join(f"- {k}: {v}" for k, v in SUBTYPE_GUIDE.items())
    prompt = EXTRACT_ENTITIES_FROM_QUESTION_PROMPT.format(
        question=question, subtype_guide=subtype_lines,
    )
    try:
        raw = await caller(prompt, model_id=model_id)
    except Exception as e:
        logger.error(f"qa: 实体抽取失败: {e}")
        return []
    return _parse_json_array(raw)


async def fetch_subgraph(
    entity_names: List[str],
    depth: int = 2,
    limit: int = 50,
) -> Dict[str, List[Dict[str, Any]]]:
    if not entity_names:
        return {"nodes": [], "edges": []}

    neo4j = Neo4jService()
    await neo4j.connect()
    try:
        async with neo4j._driver.session() as session:
            cypher = """
            MATCH (e:Entity)-[r]-(neighbor:Entity)
            WHERE e.name IN $names
            RETURN DISTINCT
                e.name AS src, e.entity_type AS src_type, e.subtype AS src_subtype,
                type(r) AS rel,
                neighbor.name AS dst, neighbor.entity_type AS dst_type, neighbor.subtype AS dst_subtype
            LIMIT $limit
            """
            r = await session.run(cypher, names=entity_names, limit=limit)
            rows = await r.data()

        nodes_set: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []
        for row in rows:
            for prefix in ("src", "dst"):
                n = row.get(prefix)
                if n and n not in nodes_set:
                    nodes_set[n] = {
                        "id": n, "name": n,
                        "type": row.get(f"{prefix}_type") or "Entity",
                        "subtype": row.get(f"{prefix}_subtype"),
                    }
            edges.append({
                "source": row["src"], "target": row["dst"], "type": row["rel"],
            })
        for n in entity_names:
            if n not in nodes_set:
                nodes_set[n] = {"id": n, "name": n, "type": "Entity", "subtype": None}

        return {"nodes": list(nodes_set.values()), "edges": edges}
    finally:
        await neo4j.close()
```

- [ ] **Step 4: 跑测试通过**

Run: `cd backend && python -m pytest tests/services/kg/test_qa.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 提交**

```bash
cd /home/aircas/AI/AI\ Studio
git add backend/app/services/kg/qa.py backend/tests/services/kg/test_qa.py
git commit -m "feat(kg): qa.py 实体抽取与子图查询"
```

---

## Task 6: qa.py — answer_question 完整流程

**Files:**
- Modify: `backend/app/services/kg/qa.py`
- Modify: `backend/tests/services/kg/test_qa.py`

- [ ] **Step 1: 追加测试**

```python
# backend/tests/services/kg/test_qa.py — 追加
from app.services.kg.qa import answer_question

@pytest.mark.asyncio
async def test_answer_question_happy_path(monkeypatch):
    async def mock_llm(prompt, **kwargs):
        if "JSON 数组" in prompt:
            return '[{"name": "OpenAI", "type": "ORGANIZATION", "subtype": "COMPANY"}]'
        return "OpenAI 成立于 2015 年[1]。"
    result = await answer_question("OpenAI 啥时候成立?", model_id="x", llm_caller=mock_llm)
    assert result["status"] == "ok"
    assert "OpenAI" in result["answer"]
    assert "OpenAI" in result["cited_entities"]

@pytest.mark.asyncio
async def test_answer_question_degraded_on_extract_failure():
    async def mock_llm(prompt, **kwargs):
        if "JSON 数组" in prompt:
            raise RuntimeError("LLM 挂")
        return "普通回答"
    result = await answer_question("?", model_id="x", llm_caller=mock_llm)
    assert result["status"] == "degraded"
    assert result["subgraph"] is None
```

- [ ] **Step 2: 跑测试失败**

Run: `cd backend && python -m pytest tests/services/kg/test_qa.py::test_answer_question_happy_path -v`
Expected: FAIL

- [ ] **Step 3: 实现 answer_question**

```python
# backend/app/services/kg/qa.py — 追加
from app.services.kg.prompts import ANSWER_WITH_GRAPH_PROMPT


def _format_subgraph_as_context(subgraph: Dict[str, List]) -> str:
    if not subgraph["nodes"]:
        return "(无相关图谱事实)"
    lines = [f"- {e['source']} --[{e['type']}]--> {e['target']}" for e in subgraph["edges"]]
    return "\n".join(lines) if lines else "(实体存在,但无相关关系)"


async def answer_question(
    question: str,
    model_id: str,
    session_id: Optional[str] = None,
    llm_caller: Optional[LlmCaller] = None,
) -> Dict[str, Any]:
    caller = llm_caller or _default_llm_caller

    entities = await extract_entities_from_question(question, model_id, llm_caller=caller)
    if not entities:
        try:
            fallback = await caller(question, model_id=model_id)
        except Exception:
            fallback = "抱歉,暂时无法回答。"
        return {
            "status": "degraded",
            "answer": fallback,
            "subgraph": None,
            "sources": [],
            "cited_entities": [],
        }

    entity_names = list({e["name"] for e in entities})
    subgraph = await fetch_subgraph(entity_names, depth=2)
    context = _format_subgraph_as_context(subgraph)
    answer_prompt = ANSWER_WITH_GRAPH_PROMPT.format(context=context, question=question)
    try:
        answer = await caller(answer_prompt, model_id=model_id)
    except Exception as e:
        logger.error(f"qa: 答案生成失败: {e}")
        answer = f"图谱检索成功,但生成回答时出错: {e}"

    return {
        "status": "ok",
        "answer": answer,
        "subgraph": subgraph,
        "sources": [],
        "cited_entities": entity_names,
    }
```

- [ ] **Step 4: 跑测试通过**

Run: `cd backend && python -m pytest tests/services/kg/test_qa.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 提交**

```bash
cd /home/aircas/AI/AI\ Studio
git add backend/app/services/kg/qa.py backend/tests/services/kg/test_qa.py
git commit -m "feat(kg): answer_question 完整流程 + 降级"
```

---

## Task 7: /api/kg/qa/answer 与 /api/kg/entity-context 端点

**Files:**
- Modify: `backend/app/api/kg.py`
- Create: `backend/tests/api/test_kg_qa.py`

- [ ] **Step 1: 写测试**

```python
# backend/tests/api/test_kg_qa.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_qa_answer_endpoint(monkeypatch):
    from app.services.kg import qa as qa_mod
    async def mock_answer(**kwargs):
        return {"status": "ok", "answer": "x", "subgraph": {"nodes": [], "edges": []}, "sources": [], "cited_entities": []}
    monkeypatch.setattr(qa_mod, "answer_question", mock_answer)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/kg/qa/answer", json={
            "question": "OpenAI 啥时候成立?",
            "model_id": "gpt-4o-mini",
        })
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"

@pytest.mark.asyncio
async def test_entity_context_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/kg/entity-context/OpenAI?limit=3")
    assert r.status_code == 200
    data = r.json()
    assert "entity" in data
    assert "articles" in data
    assert isinstance(data["articles"], list)
```

- [ ] **Step 2: 跑测试失败**

Run: `cd backend && python -m pytest tests/api/test_kg_qa.py -v`
Expected: 404

- [ ] **Step 3: 在 kg.py 顶部加 import**

```python
from pydantic import BaseModel
from app.services.kg.qa import answer_question

class QARequest(BaseModel):
    question: str
    model_id: str = "gpt-4o-mini"
    session_id: Optional[str] = None
```

- [ ] **Step 4: 在 kg.py 末尾追加端点**

```python
@router.post("/qa/answer")
async def kg_qa_answer(req: QARequest):
    """对话页 KG 问答入口"""
    try:
        return await answer_question(
            question=req.question,
            model_id=req.model_id,
            session_id=req.session_id,
        )
    except Exception as e:
        logger.error(f"qa/answer 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity-context/{entity_name}")
async def get_entity_context(
    entity_name: str,
    limit: int = Query(default=5, ge=1, le=20)
):
    """获取实体的原文出处"""
    from app.models.article import Article
    from app.core.database import SessionLocal

    neo4j = Neo4jService()
    await neo4j.connect()
    try:
        async with neo4j._driver.session() as session:
            r = await session.run(
                "MATCH (e:Entity {name:$n}) "
                "RETURN e.name AS name, e.entity_type AS type, "
                "e.subtype AS subtype, e.description AS description, "
                "e.source_articles AS source_articles",
                n=entity_name,
            )
            row = await r.single()
        if not row:
            return {"entity": {"name": entity_name, "type": None, "subtype": None, "description": None}, "articles": []}

        article_ids = (row["source_articles"] or [])[:limit]
        articles_out = []
        if article_ids:
            db = SessionLocal()
            try:
                arts = db.query(Article).filter(Article.id.in_(article_ids)).all()
                for a in arts:
                    text = (a.content or "") + " " + (a.summary or "")
                    positions = []
                    if entity_name and entity_name in text:
                        start = 0
                        while True:
                            idx = text.find(entity_name, start)
                            if idx < 0:
                                break
                            positions.append([idx, idx + len(entity_name)])
                            start = idx + len(entity_name)
                    snippet = ""
                    if positions:
                        s, e = positions[0]
                        snippet = text[max(0, s - 60):min(len(text), e + 60)]
                    articles_out.append({
                        "article_id": str(a.id),
                        "title": a.title or "(无标题)",
                        "snippet": snippet,
                        "highlight_positions": positions[:5],
                    })
            finally:
                db.close()

        return {
            "entity": {
                "name": row["name"], "type": row["type"],
                "subtype": row["subtype"], "description": row["description"],
            },
            "articles": articles_out,
        }
    finally:
        await neo4j.close()
```

- [ ] **Step 5: 跑测试通过**

Run: `cd backend && python -m pytest tests/api/test_kg_qa.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: 重启后端验证**

```bash
# 在 terminal 7 内 Ctrl-C 停掉旧 uvicorn
cd /home/aircas/AI/AI\ Studio/backend && python3 -m uvicorn app.main:app --port 8080 --host 0.0.0.0 --reload &
sleep 2
curl -s -X POST http://localhost:8080/api/kg/qa/answer \
  -H "Content-Type: application/json" \
  -d '{"question":"OpenAI 啥时候成立?","model_id":"gpt-4o-mini"}' | python3 -m json.tool
```

Expected: 返回 JSON 包含 status/answer/subgraph

- [ ] **Step 7: 提交**

```bash
cd /home/aircas/AI/AI\ Studio
git add backend/app/api/kg.py backend/tests/api/test_kg_qa.py
git commit -m "feat(kg): /qa/answer 与 /entity-context 端点"
```

---

## Task 8: 前端 api-kg.ts API 客户端

**Files:**
- Create: `frontend/src/lib/api-kg.ts`

- [ ] **Step 1: 写文件**

```typescript
// frontend/src/lib/api-kg.ts
export interface GraphNode {
  id: string;
  name: string;
  type: string;
  subtype?: string | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

export interface SourceArticle {
  article_id: string;
  title: string;
  snippet: string;
  highlight_positions: [number, number][];
}

export interface EntityInfo {
  name: string;
  type: string | null;
  subtype: string | null;
  description: string | null;
}

export interface AnswerResponse {
  status: "ok" | "degraded";
  answer: string;
  subgraph: { nodes: GraphNode[]; edges: GraphEdge[] } | null;
  sources: SourceArticle[];
  cited_entities: string[];
}

export interface EntityContextResponse {
  entity: EntityInfo;
  articles: SourceArticle[];
}

const BASE = "/api/kg";

export async function qaAnswer(
  question: string,
  modelId: string,
  sessionId?: string,
): Promise<AnswerResponse> {
  const r = await fetch(`${BASE}/qa/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, model_id: modelId, session_id: sessionId }),
  });
  if (!r.ok) throw new Error(`qa/answer failed: ${r.status}`);
  return r.json();
}

export async function getEntityContext(
  name: string,
  limit = 5,
): Promise<EntityContextResponse> {
  const r = await fetch(
    `${BASE}/entity-context/${encodeURIComponent(name)}?limit=${limit}`,
  );
  if (!r.ok) throw new Error(`entity-context failed: ${r.status}`);
  return r.json();
}
```

- [ ] **Step 2: TypeScript 类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无新错误

- [ ] **Step 3: 提交**

```bash
cd /home/aircas/AI/AI\ Studio
git add frontend/src/lib/api-kg.ts
git commit -m "feat(kg): 前端 api-kg 客户端"
```

---

## Task 9: chat-store 加 kgEnhanced 状态

**Files:**
- Modify: `frontend/src/stores/chat-store.ts`

- [ ] **Step 1: 修改 store**

在 `interface ChatStore` 内 `isStreaming: boolean;` 附近加字段:

```typescript
kgEnhanced: boolean;
setKgEnhanced: (v: boolean) => void;
```

在 store 创建内 `setStreaming:` 附近添加:

```typescript
kgEnhanced: false,
setKgEnhanced: (v) => set({ kgEnhanced: v }),
```

- [ ] **Step 2: 类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无新错误

- [ ] **Step 3: 提交**

```bash
cd /home/aircas/AI/AI\ Studio
git add frontend/src/stores/chat-store.ts
git commit -m "feat(chat): kgEnhanced 状态"
```

---

## Task 10: MiniGraph 嵌入子图组件

**Files:**
- Create: `frontend/src/components/kg/MiniGraph.tsx`

- [ ] **Step 1: 写文件**

```tsx
// frontend/src/components/kg/MiniGraph.tsx
"use client";
import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { GraphNode, GraphEdge } from "@/lib/api-kg";

const colorMap: Record<string, string> = {
  PERSON: "#10b981",
  ORGANIZATION: "#3b82f6",
  LOCATION: "#f59e0b",
  TECHNOLOGY: "#8b5cf6",
  EVENT: "#ec4899",
  CONCEPT: "#06b6d4",
  DATE: "#6b7280",
  Article: "#64748b",
};

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick?: (node: GraphNode) => void;
}

export default function MiniGraph({ nodes, edges, onNodeClick }: Props) {
  const ref = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    if (!ref.current || nodes.length === 0) return;
    const svg = d3.select(ref.current);
    svg.selectAll("*").remove();

    const width = ref.current.clientWidth || 600;
    const height = 280;

    const sim = d3
      .forceSimulation(nodes as any)
      .force("link", d3.forceLink(edges as any).id((d: any) => d.id).distance(80))
      .force("charge", d3.forceManyBody().strength(-200))
      .force("center", d3.forceCenter(width / 2, height / 2));

    const link = svg.append("g")
      .selectAll("line").data(edges).join("line")
      .attr("stroke", "#94a3b8").attr("stroke-width", 1).attr("stroke-opacity", 0.6);

    const node = svg.append("g")
      .selectAll("g").data(nodes).join("g")
      .style("cursor", "pointer")
      .on("click", (_e, d) => onNodeClick?.(d as GraphNode));

    node.append("circle")
      .attr("r", 14)
      .attr("fill", (d) => colorMap[d.type] || "#64748b")
      .attr("stroke", "#fff").attr("stroke-width", 2);

    node.append("text")
      .text((d) => d.name)
      .attr("x", 0).attr("y", 28)
      .attr("text-anchor", "middle").attr("font-size", 11).attr("fill", "#1e293b");

    node.call(
      d3.drag<any, any>()
        .on("start", (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
        .on("drag", (e, d) => { d.fx = e.x; d.fy = e.y; })
        .on("end", (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }) as any,
    );

    sim.on("tick", () => {
      link
        .attr("x1", (d: any) => d.source.x).attr("y1", (d: any) => d.source.y)
        .attr("x2", (d: any) => d.target.x).attr("y2", (d: any) => d.target.y);
      node.attr("transform", (d: any) => `translate(${d.x},${d.y})`);
    });

    return () => { sim.stop(); };
  }, [nodes, edges, onNodeClick]);

  if (nodes.length === 0) {
    return <div className="text-xs text-slate-400 italic px-2 py-3 text-center">(图谱中暂无相关实体)</div>;
  }
  return <svg ref={ref} className="w-full" style={{ height: 280 }} />;
}
```

- [ ] **Step 2: 类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无新错误

- [ ] **Step 3: 提交**

```bash
cd /home/aircas/AI/AI\ Studio
git add frontend/src/components/kg/MiniGraph.tsx
git commit -m "feat(kg): MiniGraph 嵌入子图组件"
```

---

## Task 11: EntitySourcePopover 节点出处弹窗

**Files:**
- Create: `frontend/src/components/kg/EntitySourcePopover.tsx`

- [ ] **Step 1: 写文件**

```tsx
// frontend/src/components/kg/EntitySourcePopover.tsx
"use client";
import { useEffect, useState } from "react";
import { ExternalLink, X, Loader2 } from "lucide-react";
import { getEntityContext, type EntityContextResponse } from "@/lib/api-kg";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface Props {
  entityName: string;
  onClose: () => void;
  onJumpToArticle?: (articleId: string) => void;
}

const colorMap: Record<string, string> = {
  PERSON: "bg-emerald-100 text-emerald-700",
  ORGANIZATION: "bg-blue-100 text-blue-700",
  LOCATION: "bg-amber-100 text-amber-700",
  TECHNOLOGY: "bg-violet-100 text-violet-700",
  EVENT: "bg-pink-100 text-pink-700",
  CONCEPT: "bg-cyan-100 text-cyan-700",
  DATE: "bg-slate-100 text-slate-700",
};

function highlightSnippet(snippet: string, entityName: string) {
  if (!snippet || !entityName) return snippet;
  const parts = snippet.split(new RegExp(`(${entityName})`, "gi"));
  return parts.map((p, i) =>
    p.toLowerCase() === entityName.toLowerCase() ? (
      <mark key={i} className="bg-yellow-200 px-0.5 rounded">{p}</mark>
    ) : (
      <span key={i}>{p}</span>
    ),
  );
}

export default function EntitySourcePopover({ entityName, onClose, onJumpToArticle }: Props) {
  const [data, setData] = useState<EntityContextResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getEntityContext(entityName, 5)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && console.error(e))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [entityName]);

  return (
    <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-slate-800">{entityName}</h3>
            {data?.entity?.type && (
              <Badge className={colorMap[data.entity.type] || "bg-slate-100 text-slate-700"}>
                {data.entity.type}{data.entity.subtype ? ` · ${data.entity.subtype}` : ""}
              </Badge>
            )}
          </div>
          <Button size="icon" variant="ghost" onClick={onClose}><X className="h-4 w-4" /></Button>
        </div>
        <div className="flex-1 overflow-auto p-4 space-y-3">
          {loading ? (
            <div className="flex items-center justify-center py-8 text-slate-400">
              <Loader2 className="h-5 w-5 animate-spin mr-2" />加载中…
            </div>
          ) : !data || data.articles.length === 0 ? (
            <p className="text-sm text-slate-400 italic text-center py-6">图谱中暂无该实体的原文出处</p>
          ) : (
            data.articles.map((a) => (
              <div key={a.article_id} className="border border-slate-200 rounded-md p-3 hover:border-blue-400 transition">
                <div className="flex items-start justify-between gap-2">
                  <div className="font-medium text-sm text-slate-800">{a.title}</div>
                  {onJumpToArticle && (
                    <Button size="sm" variant="ghost" onClick={() => onJumpToArticle(a.article_id)} className="text-blue-600 hover:text-blue-800 h-7 px-2">
                      <ExternalLink className="h-3 w-3 mr-1" />在文章中查看
                    </Button>
                  )}
                </div>
                {a.snippet && (
                  <p className="mt-2 text-xs text-slate-600 leading-relaxed">…{highlightSnippet(a.snippet, entityName)}…</p>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无新错误

- [ ] **Step 3: 提交**

```bash
cd /home/aircas/AI/AI\ Studio
git add frontend/src/components/kg/EntitySourcePopover.tsx
git commit -m "feat(kg): EntitySourcePopover 节点出处弹窗"
```

---

## Task 12: ChatPage 集成 KG 增强 — Switch + 分支逻辑

**Files:**
- Modify: `frontend/src/app/page.tsx`
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: 修改 types**

```typescript
// frontend/src/types/index.ts
import type { AnswerResponse } from "@/lib/api-kg";

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt?: string;
  kg?: AnswerResponse;
}
```

- [ ] **Step 2: 引入新依赖到 page.tsx**

```typescript
import { Switch } from "@/components/ui/switch";
import { Brain } from "lucide-react";
import { qaAnswer } from "@/lib/api-kg";
import MiniGraph from "@/components/kg/MiniGraph";
import EntitySourcePopover from "@/components/kg/EntitySourcePopover";
```

- [ ] **Step 3: 取出 kgEnhanced**

```typescript
const kgEnhanced = useChatStore((s) => s.kgEnhanced);
const setKgEnhanced = useChatStore((s) => s.setKgEnhanced);
const [popoverEntity, setPopoverEntity] = useState<string | null>(null);
```

- [ ] **Step 4: 包装发送函数**

```typescript
async function handleSend() {
  if (!input.trim()) return;
  const userText = input.trim();
  setInput("");
  addMessage({ id: crypto.randomUUID(), role: "user", content: userText });

  if (kgEnhanced) {
    const tmpId = crypto.randomUUID();
    addMessage({ id: tmpId, role: "assistant", content: "" });
    try {
      const data = await qaAnswer(userText, selectedModel);
      useChatStore.setState((s) => {
        const sess = s.sessions.find((x) => x.id === currentSessionId);
        if (!sess) return s;
        const msgs = [...sess.messages];
        const idx = msgs.findIndex((m) => m.id === tmpId);
        if (idx >= 0) msgs[idx] = { ...msgs[idx], content: data.answer, kg: data };
        return {
          sessions: s.sessions.map((x) =>
            x.id === currentSessionId ? { ...x, messages: msgs } : x,
          ),
        };
      });
    } catch (e: any) {
      useChatStore.setState((s) => {
        const sess = s.sessions.find((x) => x.id === currentSessionId);
        if (!sess) return s;
        const msgs = [...sess.messages];
        const idx = msgs.findIndex((m) => m.id === tmpId);
        if (idx >= 0) msgs[idx] = { ...msgs[idx], content: `错误: ${e.message}` };
        return {
          sessions: s.sessions.map((x) =>
            x.id === currentSessionId ? { ...x, messages: msgs } : x,
          ),
        };
      });
    }
    return;
  }

  await sendMessage(userText);
}
```

- [ ] **Step 5: 加 Switch UI**

在输入框上方:

```tsx
<div className="flex items-center gap-2 mb-2 px-1">
  <Switch id="kg-enhanced" checked={kgEnhanced} onCheckedChange={setKgEnhanced} />
  <label htmlFor="kg-enhanced" className="flex items-center gap-1.5 text-xs text-slate-600 cursor-pointer select-none">
    <Brain className="h-3.5 w-3.5 text-violet-600" />
    知识图谱增强 (回答包含图谱子图 + 原文出处)
  </label>
</div>
```

- [ ] **Step 6: 改发送按钮 onClick 为 handleSend**

- [ ] **Step 7: 增强消息渲染**

在消息 map 节点 assistant 消息下方:

```tsx
{msg.role === "assistant" && msg.kg && (
  <div className="mt-3 space-y-2">
    {msg.kg.subgraph && msg.kg.subgraph.nodes.length > 0 && (
      <div className="border border-slate-200 rounded-md bg-slate-50 overflow-hidden">
        <div className="text-xs text-slate-500 px-3 py-1.5 border-b bg-white">
          图谱子图 ({msg.kg.subgraph.nodes.length} 节点 / {msg.kg.subgraph.edges.length} 关系)
        </div>
        <MiniGraph
          nodes={msg.kg.subgraph.nodes}
          edges={msg.kg.subgraph.edges}
          onNodeClick={(n) => setPopoverEntity(n.name)}
        />
      </div>
    )}
    {msg.kg.sources.length > 0 && (
      <div className="border border-slate-200 rounded-md p-2 text-xs">
        <div className="text-slate-500 mb-1">引用来源</div>
        {msg.kg.sources.map((s, i) => (
          <div key={s.article_id} className="text-slate-700">[{i + 1}] {s.title}</div>
        ))}
      </div>
    )}
  </div>
)}
```

组件末尾加 Popover:

```tsx
{popoverEntity && (
  <EntitySourcePopover
    entityName={popoverEntity}
    onClose={() => setPopoverEntity(null)}
    onJumpToArticle={(id) => {
      setPopoverEntity(null);
      window.location.href = `/articles?highlight=${encodeURIComponent(popoverEntity)}&article=${id}`;
    }}
  />
)}
```

- [ ] **Step 8: 类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无新错误

- [ ] **Step 9: 手工验证 (M1 验收)**
- [ ] 打开开关,输入 "OpenAI 啥时候成立" → 看到子图 + 回答
- [ ] 关闭开关,同问题 → 走原流式
- [ ] 点击子图节点 → Popover 显示文章 + 片段高亮
- [ ] 点击 "在文章中查看" → 跳到 `/articles?highlight=OpenAI`

- [ ] **Step 10: 提交**

```bash
cd /home/aircas/AI/AI\ Studio
git add frontend/src/app/page.tsx frontend/src/types/index.ts
git commit -m "feat(chat): 集成 KG 增强开关 + 增强消息渲染"
```

---

# Milestone 2 — URL query + 文章页高亮

## Task 13: 老数据 source_articles 回溯脚本

**Files:**
- Create: `backend/scripts/kg_backfill_sources.py`

- [ ] **Step 1: 写脚本**

```python
# backend/scripts/kg_backfill_sources.py
"""回溯老实体节点的 source_articles 字段"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.kg import Neo4jService  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models.article import Article  # noqa: E402


async def backfill() -> dict:
    neo4j = Neo4jService()
    await neo4j.connect()
    try:
        async with neo4j._driver.session() as s:
            r = await s.run(
                "MATCH (e:Entity) WHERE e.entity_type IS NOT NULL "
                "RETURN e.name AS name, e.source_articles AS old"
            )
            rows = await r.data()

        db = SessionLocal()
        try:
            arts = db.query(Article).all()
        finally:
            db.close()

        updated = 0
        async with neo4j._driver.session() as s:
            for row in rows:
                name = row["name"]
                old = row["old"] or []
                if old or not name or len(name) < 2:
                    continue
                hits = []
                for a in arts:
                    text = (a.content or "") + " " + (a.summary or "")
                    if name in text:
                        hits.append(str(a.id))
                    if len(hits) >= 50:
                        break
                if hits:
                    await s.run(
                        "MATCH (e:Entity {name:$n}) SET e.source_articles = $ids",
                        n=name, ids=hits,
                    )
                    updated += 1
        return {"scanned": len(rows), "updated": updated}
    finally:
        await neo4j.close()


async def main():
    result = await backfill()
    print(f"扫描实体: {result['scanned']}")
    print(f"回溯更新: {result['updated']}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 跑脚本**

Run: `cd backend && python scripts/kg_backfill_sources.py`
Expected: "回溯更新: N" (N > 0)

- [ ] **Step 3: 验证**

```bash
cd backend && python -c "
import asyncio
from app.services.kg import Neo4jService
async def main():
    n = Neo4jService(); await n.connect()
    async with n._driver.session() as s:
        r = await s.run('MATCH (e:Entity) WHERE e.source_articles IS NOT NULL AND size(e.source_articles) > 0 RETURN count(e) AS c')
        print('有 source_articles 的实体数:', (await r.single())['c'])
    await n.close()
asyncio.run(main())
"
```

Expected: 数字 > 0

- [ ] **Step 4: 提交**

```bash
cd /home/aircas/AI/AI\ Studio
git add backend/scripts/kg_backfill_sources.py
git commit -m "feat(kg): 老数据 source_articles 回溯脚本"
```

---

## Task 14: HighlightOverlay 浮窗组件

**Files:**
- Create: `frontend/src/components/articles/HighlightOverlay.tsx`

- [ ] **Step 1: 写文件**

```tsx
// frontend/src/components/articles/HighlightOverlay.tsx
"use client";
import { ChevronUp, ChevronDown, X } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  entityName: string;
  total: number;
  current: number;
  onPrev: () => void;
  onNext: () => void;
  onClose: () => void;
}

export default function HighlightOverlay({ entityName, total, current, onPrev, onNext, onClose }: Props) {
  if (total === 0) {
    return (
      <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-amber-100 border border-amber-300 text-amber-800 text-sm px-4 py-2 rounded-md shadow-md flex items-center gap-2">
        <span>未在文中找到 "{entityName}"</span>
        <Button size="icon" variant="ghost" onClick={onClose} className="h-5 w-5"><X className="h-3 w-3" /></Button>
      </div>
    );
  }
  return (
    <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-yellow-100 border border-yellow-300 text-yellow-900 text-sm px-3 py-1.5 rounded-md shadow-md flex items-center gap-2">
      <span className="font-medium">{entityName}</span>
      <span className="text-yellow-700">·</span>
      <span>第 {current} / {total} 处</span>
      <Button size="icon" variant="ghost" onClick={onPrev} disabled={current <= 1} className="h-6 w-6" title="上一处"><ChevronUp className="h-3.5 w-3.5" /></Button>
      <Button size="icon" variant="ghost" onClick={onNext} disabled={current >= total} className="h-6 w-6" title="下一处"><ChevronDown className="h-3.5 w-3.5" /></Button>
      <Button size="icon" variant="ghost" onClick={onClose} className="h-6 w-6" title="关闭"><X className="h-3.5 w-3.5" /></Button>
    </div>
  );
}
```

- [ ] **Step 2: 类型检查 + 提交**

```bash
cd /home/aircas/AI/AI\ Studio
git add frontend/src/components/articles/HighlightOverlay.tsx
git commit -m "feat(articles): HighlightOverlay 浮窗"
```

---

## Task 15: 文章页 URL query + 高亮

**Files:**
- Modify: `frontend/src/app/articles/page.tsx`
- Modify: `frontend/src/app/globals.css`

- [ ] **Step 1: 加 CSS**

```css
/* frontend/src/app/globals.css — 追加 */
mark.kg-highlight {
  background: #fef08a;
  padding: 0 2px;
  border-radius: 2px;
  transition: background 0.2s;
}
mark.kg-highlight.active {
  background: #facc15;
  outline: 2px solid #eab308;
}
```

- [ ] **Step 2: 在 articles/page.tsx 顶部 imports 添加**

```typescript
import { useSearchParams, useRouter } from "next/navigation";
import HighlightOverlay from "@/components/articles/HighlightOverlay";
```

- [ ] **Step 3: 在 ArticlesPage 函数体内加 highlight 逻辑**

```typescript
const searchParams = useSearchParams();
const router = useRouter();
const highlightName = searchParams.get("highlight");

const [highlights, setHighlights] = useState<HTMLElement[]>([]);
const [currentIdx, setCurrentIdx] = useState(0);

useEffect(() => {
  if (!highlightName) { setHighlights([]); return; }
  const body = document.querySelector("[data-article-body]");
  if (!body) return;
  body.querySelectorAll("mark.kg-highlight").forEach((m) => {
    m.replaceWith(document.createTextNode(m.textContent || ""));
  });
  const escaped = highlightName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(`(${escaped})`, "g");
  const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
  const nodes: Text[] = [];
  let n: Node | null;
  while ((n = walker.nextNode())) nodes.push(n as Text);
  nodes.forEach((node) => {
    const text = node.textContent || "";
    re.lastIndex = 0;
    if (!re.test(text)) return;
    re.lastIndex = 0;
    const frag = document.createDocumentFragment();
    let last = 0; let m: RegExpExecArray | null; let i = 0;
    while ((m = re.exec(text))) {
      if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)));
      const mark = document.createElement("mark");
      mark.className = "kg-highlight";
      mark.dataset.idx = String(i++);
      mark.textContent = m[0];
      frag.appendChild(mark);
      last = m.index + m[0].length;
    }
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
    node.parentNode?.replaceChild(frag, node);
  });
  const marks = Array.from(body.querySelectorAll<HTMLElement>("mark.kg-highlight"));
  setHighlights(marks);
  setCurrentIdx(0);
  if (marks[0]) marks[0].scrollIntoView({ behavior: "smooth", block: "center" });
}, [highlightName]);

useEffect(() => {
  highlights.forEach((m, i) => m.classList.toggle("active", i === currentIdx));
  if (highlights[currentIdx]) highlights[currentIdx].scrollIntoView({ behavior: "smooth", block: "center" });
}, [currentIdx, highlights]);

function clearHighlight() {
  const body = document.querySelector("[data-article-body]");
  if (body) body.querySelectorAll("mark.kg-highlight").forEach((m) => {
    m.replaceWith(document.createTextNode(m.textContent || ""));
  });
  setHighlights([]);
  const url = new URL(window.location.href);
  url.searchParams.delete("highlight");
  router.replace(url.pathname + (url.search || ""));
}
```

- [ ] **Step 4: 渲染 HighlightOverlay**

在文章详情 JSX 最外层 `<div>` 内(已选中文章时):

```tsx
{highlightName && (
  <HighlightOverlay
    entityName={highlightName}
    total={highlights.length}
    current={highlights.length > 0 ? currentIdx + 1 : 0}
    onPrev={() => setCurrentIdx((i) => Math.max(0, i - 1))}
    onNext={() => setCurrentIdx((i) => Math.min(highlights.length - 1, i + 1))}
    onClose={clearHighlight}
  />
)}
```

- [ ] **Step 5: 给文章正文容器加 data-article-body 属性**

找到文章正文 `<div>`(渲染 `article.content` 的位置),加属性:

```tsx
<div data-article-body className="prose ...">
  {article.content}
</div>
```

- [ ] **Step 6: 类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无新错误

- [ ] **Step 7: 手工验证 (M2 验收)**
- [ ] `/articles?highlight=OpenAI` → 自动滚动 + 高亮
- [ ] 浮窗 ▲/▼ → 切换上/下一处
- [ ] × → 清除高亮

- [ ] **Step 8: 提交**

```bash
cd /home/aircas/AI/AI\ Studio
git add frontend/src/app/articles/page.tsx frontend/src/app/globals.css
git commit -m "feat(articles): URL query + 全文高亮 + 浮窗"
```

---

## Task 16: /kg 页节点共用 Popover

**Files:**
- Modify: `frontend/src/app/kg/page.tsx`

- [ ] **Step 1: 加 import**

```typescript
import { useState } from "react";
import EntitySourcePopover from "@/components/kg/EntitySourcePopover";
```

- [ ] **Step 2: 加 state**

```typescript
const [popoverEntity, setPopoverEntity] = useState<string | null>(null);
```

- [ ] **Step 3: 在 D3 节点 click 处改为 setPopoverEntity**

找到 `kg/page.tsx` 中 D3 节点 click 处理器,改为:

```typescript
.on("click", (_e, d) => setPopoverEntity(d.name as string))
```

- [ ] **Step 4: 组件末尾渲染 Popover**

```tsx
{popoverEntity && (
  <EntitySourcePopover
    entityName={popoverEntity}
    onClose={() => setPopoverEntity(null)}
    onJumpToArticle={(id) => {
      setPopoverEntity(null);
      window.location.href = `/articles?highlight=${encodeURIComponent(popoverEntity)}&article=${id}`;
    }}
  />
)}
```

- [ ] **Step 5: 类型检查 + 提交**

```bash
cd /home/aircas/AI/AI\ Studio
git add frontend/src/app/kg/page.tsx
git commit -m "feat(kg): /kg 页节点共用 EntitySourcePopover"
```

---

## Self-Review

1. **Spec coverage:**
   - M1 数据评估 → Task 1 ✓
   - M1 EntityNode.source_articles → Task 2 ✓
   - M1 extractor 记录来源 → Task 3 ✓
   - M1 prompts → Task 4 ✓
   - M1 qa.py 实体抽取/子图 → Task 5 ✓
   - M1 answer_question → Task 6 ✓
   - M1 /qa/answer 端点 → Task 7 ✓
   - M1 /entity-context 端点 → Task 7 ✓
   - M1 前端 api-kg → Task 8 ✓
   - M1 chat-store → Task 9 ✓
   - M1 MiniGraph → Task 10 ✓
   - M1 EntitySourcePopover → Task 11 ✓
   - M1 ChatPage 集成 → Task 12 ✓
   - M2 回溯脚本 → Task 13 ✓
   - M2 HighlightOverlay → Task 14 ✓
   - M2 文章页 URL + 高亮 → Task 15 ✓
   - M2 /kg 页共用 Popover → Task 16 ✓

2. **Placeholder scan:** 无 TBD / TODO / "implement later" / "appropriate error handling" 等占位词。所有代码块完整可执行。

3. **Type consistency:**
   - `AnswerResponse` 在 `api-kg.ts` 定义,Tasks 8/9/12 引用一致
   - `EntityContextResponse` 在 `api-kg.ts` 定义,Task 11 引用一致
   - `kgEnhanced` 在 chat-store 定义 (Task 9),Task 12 引用一致
   - `popoverEntity` 在 page.tsx (Task 12) 和 kg/page.tsx (Task 16) 都用 useState<string | null>
   - `data-article-body` 属性在 Task 15 定义,Task 15 自身使用

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-07-09-kg-qa-in-chat-plan.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - 每个 Task 派一个 fresh subagent,任务间 review,快速迭代
**2. Inline Execution** - 当前 session 顺序执行,带 checkpoint

请选择执行方式。
