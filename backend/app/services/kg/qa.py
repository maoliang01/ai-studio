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
    """从 LLM 输出中抠出 JSON 数组(允许前后有杂字)"""
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
