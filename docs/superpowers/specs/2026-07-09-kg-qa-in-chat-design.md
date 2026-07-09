# 对话页知识图谱问答 & 原文出处溯源 - 设计文档

**日期**: 2026-07-09
**状态**: 待用户审阅
**作者**: brainstorm session
**关联模块**: `frontend/src/app/page.tsx`, `backend/app/services/kg/*`, `frontend/src/app/articles/page.tsx`

---

## 1. 背景与目标

### 1.1 现状
- 知识图谱已构建完成:Neo4j 中已存有 7 大类实体 (PERSON / ORGANIZATION / LOCATION / TECHNOLOGY / EVENT / CONCEPT / DATE) 与对应 subtype(50+ 种细分),通过 `batch_create_entities_and_relations` 写入。
- 对话页 (`/`) 与图谱页 (`/kg`) 相互独立,图谱查询能力未在对话场景中暴露。
- 用户提出三点诉求:
  1. 在对话页**自动**调用图谱,辅助回答
  2. 抽取实体带**原文出处**
  3. 节点点击可**跳回原文高亮**

### 1.2 目标
在**不新建独立对话页**的前提下,集成 KG 能力到现有 ChatPage:
- 用户可一键开关"知识图谱增强"
- 开启后,回答同时包含:LLM 文本 + 图谱子图 + 原文出处卡片
- 节点可点击 → 看原文出处 → 一键跳到文章页**高亮**该实体所在位置

### 1.3 非目标 (YAGNI)
- Text2Cypher (LLM 自动生成 Cypher)
- 多跳推理 (3 跳以上)
- 跨会话 KG 累积记忆
- 实体消歧 embedding 方案 (仅做精确匹配)
- `/kg` 页迁入对话页 (保持独立入口)
- 改造现有 `/api/chat/stream` 端点 (新增端点,旧端点保留)

---

## 2. 使用场景

### 2.1 主场景:Alice 查公司背景

> Alice 在对话页打开「🧠 知识图谱增强」开关,问:
> **"OpenAI 是什么时候成立的?Sam Altman 之前在哪家公司?"**

**执行链路**:
1. 前端:开关亮 → `POST /api/kg/qa/answer` 携带 `{question, model_id, session_id}`
2. 后端:LLM 抽实体 → `OpenAI`, `Sam Altman`
3. Cypher:查这 2 个实体的 1-2 跳邻居
4. 三元组拼成 prompt context → LLM 生成回答
5. 返回 `{answer, subgraph, sources}`
6. 前端渲染:Markdown + mini D3 + 来源卡片

### 2.2 子场景:节点溯源

> Alice 点击 mini 图中 `OpenAI` 节点

**执行链路**:
1. 弹 `EntitySourcePopover`
2. 后端查 `Entity.source_articles` → 返回 3 篇文章的标题 + 原文片段(包含 `OpenAI` 的句子)
3. 片段中 `OpenAI` 文字**内联高亮** (`<mark>` 标签)
4. Alice 点 "在文章中查看" → 跳到 `/articles?highlight=OpenAI`

### 2.3 子场景:文章页定位

> 进入文章页后

**执行链路**:
1. URL 参数 `?highlight=OpenAI` 被解析
2. 全文搜索 "OpenAI" → 所有匹配包 `<mark class="kg-highlight">`
3. 自动滚到第一处 → 顶部浮窗显示 "OpenAI · 第 1 / N 处 [上] [下] [×]"
4. 关闭高亮:点 × 或去 URL 参数

---

## 3. 架构与数据流

```
┌────────────┐         ┌────────────────────────────────┐
│ ChatPage   │         │ Backend                         │
│ (page.tsx) │  POST   │                                 │
│  🧠 ON     │ ──────→ │ /api/kg/qa/answer               │
│            │         │   ├─ LLM extract entities       │
│            │         │   ├─ Neo4j Cypher (1-2 跳)      │
│            │         │   ├─ Build context              │
│            │         │   ├─ LLM answer                 │
│ 渲染:      │ ←────── │   └─ {answer, sub, sources}     │
│  Markdown  │         │                                 │
│  + mini图  │         │ Neo4j: Entity {source_articles} │
│  + 来源    │         │                                 │
│  + Popover │         │                                 │
└────────────┘         └────────────────────────────────┘
       │ click node
       ▼
┌─────────────────────┐
│ EntitySourcePopover │ ──→ /api/kg/entity-context/{name}
│  + 内联高亮          │      返回 {articles: [{id, title, snippet}]}
└─────────────────────┘
       │ click "在文章中查看"
       ▼
┌──────────────────────┐
│ /articles?highlight=OpenAI │
│  → 全文搜索 + 高亮      │
│  → 浮窗上下跳转         │
└──────────────────────┘
```

---

## 4. 里程碑划分

### M1 = 阶段 1 + 阶段 2
**数据评估 + 对话页 RAG + 节点 Popover 高亮**

交付物:
- `kg_health_check.py` 数据评估脚本
- `POST /api/kg/qa/answer` 端点
- `qa.py` 问答核心服务
- `MiniGraph` + `EntitySourcePopover` 组件
- 现有 ChatPage 加 `kgEnhanced` 开关
- 实体抽取时记录 `source_articles`

### M2 = 阶段 3
**URL query + 文章页高亮浮窗 + 老数据回溯**

交付物:
- `kg_backfill_sources.py` 老数据回溯
- 文章页 `?highlight=X` 解析
- `HighlightOverlay` 浮窗组件
- `/kg` 页节点共用 `EntitySourcePopover`

---

## 5. 详细设计

### 5.1 后端 - 数据层

#### 5.1.1 `EntityNode` 扩展
文件:`backend/app/services/kg/graph.py`

```python
@dataclass
class EntityNode:
    name: str
    entity_type: str
    description: Optional[str] = None
    subtype: Optional[str] = None
    source_articles: Optional[List[str]] = None  # 新增:出现该实体的文章 id 列表
```

#### 5.1.2 Neo4j 写入
`create_entity_node` 与 `batch_create_entities_and_relations`:
- `MERGE` 时 `SET e.source_articles = coalesce(e.source_articles, []) + $new_articles`
- 保证多次抽取(同实体多文章)能累积

#### 5.1.3 抽取器写入来源
文件:`backend/app/services/kg/extractor.py`
- `extract(article_id, text)` 调用时多传 `article_id`
- 写实体时自动 `source_articles = [article_id]`

### 5.2 后端 - 问答核心

#### 5.2.1 `qa.py` 服务
文件:`backend/app/services/kg/qa.py` (新)

```python
async def answer_question(
    question: str,
    model_id: str,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Returns:
        {
            "answer": "...",
            "subgraph": {"nodes": [...], "edges": [...]},
            "sources": [{"article_id": "...", "title": "...", "snippet": "..."}],
            "cited_entities": ["OpenAI", "Sam Altman"]
        }
    """
    # 1. 实体抽取
    entities = await extract_entities_from_question(question, model_id)

    # 2. Cypher 查询 1-2 跳邻居
    subgraph = await fetch_subgraph(entities, depth=2)

    # 3. 拼 context
    context = format_subgraph_as_context(subgraph)

    # 4. LLM 生成回答
    answer = await generate_answer(question, context, model_id)

    # 5. 拿来源文章
    sources = await fetch_source_snippets(entities, max_per_entity=2)

    return {...}
```

#### 5.2.2 Cypher 查询
```cypher
// 1 跳: 实体直接邻居
MATCH (e:Entity {name: $name})-[r]-(neighbor:Entity)
WHERE e.name IN $entity_names
RETURN e.name AS src, type(r) AS rel, neighbor.name AS dst,
       neighbor.entity_type AS dst_type, neighbor.subtype AS dst_subtype
LIMIT 50
```

#### 5.2.3 降级策略
- 实体抽取失败 → 返回 `answer="图谱中暂未识别到相关实体,以下是普通回答..."` + `subgraph={}` + 普通 LLM 回答
- Neo4j 不可用 → HTTP 500,前端降级为原 `/api/chat/stream`
- 无任何相关实体 → 返回 `"图谱中暂未收录相关信息"` + 空 subgraph

### 5.3 后端 - 端点

#### 5.3.1 `POST /api/kg/qa/answer`
文件:`backend/app/api/kg.py`

```python
@router.post("/qa/answer")
async def qa_answer(req: QARequest):
    return await qa_service.answer_question(
        question=req.question,
        model_id=req.model_id,
        session_id=req.session_id,
    )
```

#### 5.3.2 `GET /api/kg/entity-context/{name}`
返回 `EntitySourcePopover` 需要的数据:
```json
{
  "entity": {"name": "OpenAI", "type": "ORGANIZATION", "subtype": "COMPANY"},
  "articles": [
    {
      "article_id": "abc-123",
      "title": "AI 公司巡礼",
      "snippet": "...OpenAI 于 2015 年 12 月成立...",
      "highlight_positions": [[start, end], ...]
    }
  ]
}
```

实现:查 `Entity.source_articles` → 对每篇文章从 SQLite 拿正文 → 用正则找实体名位置 → 截 ±60 字符片段。

### 5.4 前端 - ChatPage 改造

文件:`frontend/src/app/page.tsx`

#### 5.4.1 状态
```typescript
const [kgEnhanced, setKgEnhanced] = useState(false);
```

#### 5.4.2 发送逻辑分支
```typescript
async function send() {
  if (kgEnhanced) {
    // 走 KG QA
    const res = await fetch("/api/kg/qa/answer", { method: "POST", body: ... });
    const data = await res.json();
    addMessage({ role: "assistant", content: data.answer, kg: data });
  } else {
    // 走原流式
    sendMessage(...);
  }
}
```

#### 5.4.3 渲染增强消息
在 `Message` 组件内:
- Markdown 文本
- `<MiniGraph nodes={kg.subgraph.nodes} edges={kg.subgraph.edges} />`
- 来源卡片列表
- 节点 `onClick` → `<EntitySourcePopover entity={node.name} />`

### 5.5 前端 - 新组件

#### 5.5.1 `MiniGraph.tsx`
- 基于现有 `kg/page.tsx` 的 D3 渲染逻辑
- 简化版:固定宽 100% × 高 280px,无 zoom
- 节点 click 事件向上传递 entity name

#### 5.5.2 `EntitySourcePopover.tsx`
- Popover 浮窗,鼠标点击触发
- 内容:实体基本信息 + 出现文章列表 + 片段高亮 + "在文章中查看" 按钮

#### 5.5.3 `HighlightOverlay.tsx` (M2)
- 文章页顶部浮窗:`<EntityName> · 第 <i>/<N> 处 [▲] [▼] [×]`
- 上下按钮:滚动到上一/下一处高亮
- × 按钮:清除 URL 参数 + 移除高亮

### 5.6 文章页高亮实现 (M2)

文件:`frontend/src/app/articles/page.tsx`

```typescript
const searchParams = useSearchParams();
const highlight = searchParams.get("highlight");

useEffect(() => {
  if (!highlight || !articleContent) return;
  // 1. 全文替换 entity name → <mark class="kg-highlight" data-pos={i}>
  // 2. 收集所有 mark DOM
  // 3. 滚动到第一个
}, [highlight, articleContent]);
```

CSS:
```css
.kg-highlight { background: #fef08a; padding: 0 2px; border-radius: 2px; }
.kg-highlight.active { background: #facc15; outline: 2px solid #eab308; }
```

---

## 6. 关键接口契约

### 6.1 `POST /api/kg/qa/answer`

请求:
```json
{ "question": "OpenAI 什么时候成立?", "model_id": "gpt-4o-mini", "session_id": "..." }
```

响应(成功):
```json
{
  "status": "ok",
  "answer": "OpenAI 成立于 2015 年[1]...",
  "subgraph": {
    "nodes": [
      { "id": "openai", "name": "OpenAI", "type": "ORGANIZATION", "subtype": "COMPANY" },
      { "id": "sam_altman", "name": "Sam Altman", "type": "PERSON", "subtype": "ENTREPRENEUR" }
    ],
    "edges": [
      { "source": "sam_altman", "target": "openai", "type": "FOUNDED" }
    ]
  },
  "sources": [
    { "article_id": "abc-123", "title": "AI 公司巡礼", "snippet": "OpenAI 于 2015 年 12 月..." }
  ],
  "cited_entities": ["OpenAI", "Sam Altman"]
}
```

响应(降级):
```json
{ "status": "degraded", "answer": "图谱中暂未识别...", "subgraph": null, "sources": [] }
```

### 6.2 `GET /api/kg/entity-context/{name}?limit=5`

响应:
```json
{
  "entity": { "name": "OpenAI", "type": "ORGANIZATION", "subtype": "COMPANY", "description": "..." },
  "articles": [
    {
      "article_id": "abc-123",
      "title": "AI 公司巡礼",
      "snippet": "...OpenAI 于 2015 年...",
      "highlight_positions": [[42, 48]]
    }
  ]
}
```

---

## 7. 数据评估脚本

文件:`backend/scripts/kg_health_check.py` (M1)

输出到 `reports/kg_health_<timestamp>.json`:
```json
{
  "summary": {
    "total_nodes": 1234,
    "total_relationships": 5678,
    "articles_in_kg": 89
  },
  "entity_type_distribution": { "PERSON": 234, "TECHNOLOGY": 156, ... },
  "subtype_distribution": { "SCIENTIST": 45, "AI_MODEL": 23, ... },
  "orphans": [{ "name": "...", "type": "PERSON" }, ...],  // 度=0 的实体
  "duplicate_candidates": [{ "names": ["Open AI", "OpenAI"], "similarity": 0.92 }, ...],
  "source_articles_coverage": 0.87,  // 有 source_articles 的实体占比
  "recommendations": ["补充 12 个孤立节点的关系", "合并 3 组重复实体"]
}
```

---

## 8. 错误处理

| 失败点 | 降级行为 |
|--------|---------|
| 实体抽取 LLM 失败 | 返回 `degraded` 响应,前端展示普通 LLM 回答 |
| Neo4j 不可用 | 返回 500,前端 catch 后自动改走原 `/api/chat/stream` |
| Cypher 无结果 | answer = "图谱中暂未收录相关信息",subgraph = null |
| 来源文章查询失败 | sources = [],不影响主回答 |
| 文章页高亮正则无匹配 | 显示 "未在文中找到 <EntityName>" 提示,1.5s 后自动消失 |

---

## 9. 测试策略

### 9.1 单元测试
- `qa.py` 实体抽取(用 mock LLM 响应)
- Cypher 查询(连真实 Neo4j,断言节点/边数量)
- 文章页高亮正则(已知输入 → 期望 output)
- 降级逻辑(注入各失败点)

### 9.2 集成测试
- 端到端:`POST /qa/answer` → 验响应结构
- 节点溯源:点节点 → 验 Popover 内容
- URL 跳转:`/articles?highlight=X` → 验高亮 DOM 存在

### 9.3 手工验收 (M1 完成后)
- [ ] 打开开关 → 输入 "OpenAI 什么时候成立" → 看到子图 + 回答
- [ ] 关闭开关 → 同问题 → 走原流式
- [ ] 点击子图节点 → Popover 显示文章 + 片段高亮
- [ ] 点击 "在文章中查看" → 跳到文章页 + 高亮

### 9.4 手工验收 (M2 完成后)
- [ ] 文章页 URL 加 `?highlight=OpenAI` → 自动滚动 + 高亮
- [ ] 点浮窗 ▲/▼ → 切换到上/下一处
- [ ] 点 × → 清除高亮

---

## 10. 文件清单(完整)

### M1
- `backend/scripts/kg_health_check.py` (新)
- `backend/app/services/kg/qa.py` (新)
- `backend/app/services/kg/prompts.py` (新)
- `backend/app/services/kg/graph.py` (改:EntityNode + Neo4j 写入)
- `backend/app/services/kg/extractor.py` (改:抽取时记录 source_articles)
- `backend/app/api/kg.py` (改:+ qa/answer + entity-context 端点)
- `frontend/src/app/page.tsx` (改:Switch + 分支逻辑 + 增强渲染)
- `frontend/src/components/kg/MiniGraph.tsx` (新)
- `frontend/src/components/kg/EntitySourcePopover.tsx` (新)
- `frontend/src/stores/chat-store.ts` (改:+ kgEnhanced)

### M2
- `backend/scripts/kg_backfill_sources.py` (新)
- `frontend/src/app/articles/page.tsx` (改:URL query + 高亮)
- `frontend/src/components/articles/HighlightOverlay.tsx` (新)
- `frontend/src/app/kg/page.tsx` (改:节点共用 Popover)

---

## 11. 风险与缓解

| 风险 | 缓解 |
|------|------|
| LLM 抽实体不准确(尤其中文) | 提示词加 few-shot + 兜底用关键词匹配 |
| Cypher 查询慢(>5s) | 加 `LIMIT 50`、超时返回降级 |
| 嵌入子图在窄屏体验差 | `< md` 隐藏子图,只显示回答 + 来源 |
| 老数据无 source_articles | M2 回溯脚本必须先跑 |
| 高亮匹配误伤(如匹配到 "open" 子串) | 单词边界 `\b` + 大小写敏感(用户传啥查啥) |
| 用户每条消息都开 KG → 成本 | 开关默认 OFF,提示用户主动开 |

---

## 12. 实施顺序建议

```
Day 1: 数据评估脚本 (M1.1)
Day 2: qa.py + 端点 + 后端测试 (M1.2)
Day 3: ChatPage 改造 + MiniGraph + Popover (M1.3)
Day 4: 联调 + bugfix + M1 验收
Day 5: 回溯脚本 + 文章页高亮 (M2.1-2.2)
Day 6: M2 验收 + 老数据回填 + 文档
```

---

## 附录 A:提示词草案

### 实体抽取 prompt
```
从以下问题中抽取关键实体(人名/组织/技术/地点/事件/概念/日期)。
要求:
- name: 实体原文
- type: PERSON|ORGANIZATION|LOCATION|TECHNOLOGY|EVENT|CONCEPT|DATE 之一
- subtype: 该 type 下的细分 (见下方候选)
[7 大类 50+ 候选]
只返回 JSON 数组。

问题: {question}
```

### 回答生成 prompt
```
你是基于知识图谱的问答助手。严格依据下方图谱事实回答,不要编造。
如信息不足,直接说"图谱中暂未收录"。

图谱事实:
{context}

问题: {question}
回答(末尾用 [n] 标注引用):
```

---

## 附录 B:开放问题(供实施时确认)

1. ChatPage 默认是否开启 KG 增强?(建议 OFF,避免成本浪费)
2. 子图节点数量上限多少合适?(建议 20)
3. 实体同名歧义(同名不同实体)如何处理?(M1 先不做,留 TODO)
4. 高亮浮窗在 mobile 端如何展示?(建议 M2 简化为底部 sheet)
