"""知识图谱问答服务"""
import json
import logging
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional

from app.services.kg import Neo4jService
from app.services.kg.prompts import (
    EXTRACT_ENTITIES_FROM_QUESTION_PROMPT,
    SUBTYPE_GUIDE,
    ANSWER_WITH_GRAPH_PROMPT,
)

logger = logging.getLogger("ai-studio")

LlmCaller = Callable[..., Awaitable[str]]


async def _default_llm_caller(prompt: str, model_id: str, **kwargs) -> str:
    """默认 LLM 调用:走 llm_service"""
    from app.core.llm import llm_service
    response = await llm_service.non_stream_chat(
        model_id=model_id or "default",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )
    # response 可能是 str 或 dict
    if isinstance(response, dict):
        return response.get("content", "") or json.dumps(response)
    return str(response)


def _parse_json_array(text: str) -> List[Dict[str, Any]]:
    """从 LLM 输出中抠出 JSON 数组。

    LLM 实际输出形态多样:
    - 裸 JSON: `[{"name": "X", ...}]`
    - 包在 markdown code fence: ```json\n[...]\n```
    - 带 <think>...</think> 推理标签
    - 前后有零散解释文字
    """
    if not text:
        return []
    cleaned = text.strip()
    # 去掉 <think>...</think> 推理段
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL)
    # 去掉 markdown code fence 标记(```json 或 ```)
    cleaned = re.sub(r"```(?:json|JSON)?\s*", "", cleaned)
    cleaned = cleaned.replace("```", "")
    # 找第一个 `[` 到最后一个 `]` 之间的内容(允许多行,允许内部有空格)
    m = re.search(r"\[\s*[\s\S]*\]", cleaned)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except (json.JSONDecodeError, ValueError):
        logger.warning(f"qa: 无法解析 LLM 输出: {text[:200]}")
        return []
    return [d for d in data if isinstance(d, dict) and d.get("name")]


async def extract_entities_from_question(
    question: str,
    model_id: str,
    llm_caller: Optional[LlmCaller] = None,
) -> List[Dict[str, Any]]:
    """从问题中抽取关键实体"""
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
    """根据实体名查 1-2 跳邻居子图"""
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
        # 源实体即使无邻居也加入(避免子图空)
        for n in entity_names:
            if n not in nodes_set:
                nodes_set[n] = {"id": n, "name": n, "type": "Entity", "subtype": None}

        return {"nodes": list(nodes_set.values()), "edges": edges}
    finally:
        await neo4j.close()


def _format_subgraph_as_context(subgraph: Dict[str, List]) -> str:
    """把子图序列化成 LLM 可读的 context 文本"""
    if not subgraph["nodes"]:
        return "(无相关图谱事实)"
    lines = [f"- {e['source']} --[{e['type']}]--> {e['target']}" for e in subgraph["edges"]]
    return "\n".join(lines) if lines else "(实体存在,但无相关关系)"


async def fetch_entity_sources(
    entity_name: str,
    db: Any = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """获取实体在哪些文章里出现过,以及带高亮位置的原文片段。

    Args:
        entity_name: 实体名(Neo4j Entity.name)
        db: SQLAlchemy Session(查 Article 详情需要)
        limit: 最多返回多少篇来源文章

    Returns:
        [{"article_id": str, "title": str, "snippet": str,
          "highlight_positions": [[start, end], ...]}, ...]
    """
    if not entity_name:
        return []

    # 1) 从 Neo4j 查实体的 source_articles
    neo4j = Neo4jService()
    await neo4j.connect()
    try:
        async with neo4j._driver.session() as session:
            r = await session.run(
                "MATCH (e:Entity {name:$n}) "
                "RETURN e.source_articles AS source_articles",
                n=entity_name,
            )
            row = await r.single()
        if not row or not row["source_articles"]:
            return []
        article_ids: List[str] = list(row["source_articles"])[:limit]
    finally:
        await neo4j.close()

    if not article_ids or db is None:
        return [{"article_id": aid, "title": "(未取详情)", "snippet": "",
                 "highlight_positions": []} for aid in article_ids]

    # 2) 从 SQLite 查文章详情,计算高亮位置
    from app.models.article import Article
    arts = db.query(Article).filter(Article.id.in_(article_ids)).all()
    arts_by_id = {str(a.id): a for a in arts}

    out: List[Dict[str, Any]] = []
    for aid in article_ids:
        a = arts_by_id.get(aid)
        if not a:
            out.append({"article_id": aid, "title": "(文章已删除)",
                        "snippet": "", "highlight_positions": []})
            continue
        text = (a.content or "") + " " + (a.summary or "")
        positions: List[List[int]] = []
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
        out.append({
            "article_id": str(a.id),
            "title": a.title or "(无标题)",
            "snippet": snippet,
            "highlight_positions": positions[:5],
        })
    return out


async def _aggregate_sources(
    entity_names: List[str],
    db: Any = None,
    per_entity_limit: int = 3,
    total_limit: int = 10,
) -> List[Dict[str, Any]]:
    """为多个实体汇总来源文章(去重、限总数)"""
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for name in entity_names:
        try:
            arts = await fetch_entity_sources(name, db=db, limit=per_entity_limit)
        except Exception as e:
            logger.warning(f"qa: 汇总来源失败 {name}: {e}")
            continue
        for art in arts:
            aid = art.get("article_id")
            if not aid or aid in seen:
                continue
            seen.add(aid)
            art["entity_name"] = name  # 标注是哪实体引出的
            out.append(art)
            if len(out) >= total_limit:
                return out
    return out


async def answer_question(
    question: str,
    model_id: str,
    session_id: Optional[str] = None,
    db: Any = None,
    llm_caller: Optional[LlmCaller] = None,
) -> Dict[str, Any]:
    """完整问答流程

    Args:
        db: SQLAlchemy Session(可选,传入后会查来源文章)
    """
    caller = llm_caller or _default_llm_caller

    entities = await extract_entities_from_question(question, model_id, llm_caller=caller)
    if not entities:
        # 降级:走普通 LLM 回答
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

    # 汇总来源文章(去重、按实体聚合,限 10 篇)
    sources = await _aggregate_sources(entity_names, db=db)

    return {
        "status": "ok",
        "answer": answer,
        "subgraph": subgraph,
        "sources": sources,
        "cited_entities": entity_names,
    }
