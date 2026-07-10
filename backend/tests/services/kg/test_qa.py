import pytest
from app.services.kg.qa import (
    answer_question,
    extract_entities_from_question,
    fetch_entity_sources,
)


@pytest.mark.asyncio
async def test_answer_question_happy_path():
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


@pytest.mark.asyncio
async def test_extract_entities_handles_markdown_code_fence():
    """LLM 把 JSON 包在 ```json ... ``` 里,解析器应能识别"""
    async def mock_llm(prompt, **kwargs):
        return (
            "<think>用户在问 OpenAI</think>\n\n"
            "```json\n"
            '[{"name": "OpenAI", "type": "ORGANIZATION", "subtype": "COMPANY"}]\n'
            "```"
        )
    result = await extract_entities_from_question(
        "OpenAI 啥时候成立?", model_id="x", llm_caller=mock_llm
    )
    assert len(result) == 1
    assert result[0]["name"] == "OpenAI"
    assert result[0]["type"] == "ORGANIZATION"


@pytest.mark.asyncio
async def test_extract_entities_handles_think_tags_and_markdown():
    """带 <think> 标签和 markdown code fence 的真实 LLM 输出"""
    async def mock_llm(prompt, **kwargs):
        return (
            "用户问题包含" + "习近平" + "。\n"
            "<think>这是一个人名</think>\n\n"
            "```json\n"
            '[{"name": "' + "习近平" + '", "type": "PERSON", "subtype": "POLITICIAN"}]\n'
            "```"
        )
    result = await extract_entities_from_question(
        "习近平", model_id="x", llm_caller=mock_llm
    )
    assert len(result) == 1
    assert result[0]["name"] == "习近平"
    assert result[0]["type"] == "PERSON"


@pytest.mark.asyncio
async def test_answer_question_populates_sources():
    """answer_question 应返回来源文章(去重、按文章聚合)"""
    async def mock_llm(prompt, **kwargs):
        if "JSON 数组" in prompt:
            return '[{"name": "习近平", "type": "PERSON", "subtype": "POLITICIAN"}]'
        return "根据图谱事实..."

    # 模拟 fetch_subgraph: 返回带两个 entity 的子图
    async def mock_fetch_subgraph(names, depth=2, limit=50):
        return {
            "nodes": [
                {"id": "习近平", "name": "习近平", "type": "PERSON", "subtype": "POLITICIAN"},
            ],
            "edges": [],
        }

    # 模拟 fetch_entity_sources: 返回两篇文章
    async def mock_fetch_entity_sources(name, db=None, limit=5):
        return [
            {"article_id": "a1", "title": "文章1", "snippet": "提到习近平",
             "highlight_positions": [[0, 0]]},
            {"article_id": "a2", "title": "文章2", "snippet": "也提到习近平",
             "highlight_positions": [[0, 0]]},
        ]

    from app.services.kg import qa as qa_mod
    orig_subgraph = qa_mod.fetch_subgraph
    orig_sources = qa_mod.fetch_entity_sources
    qa_mod.fetch_subgraph = mock_fetch_subgraph
    qa_mod.fetch_entity_sources = mock_fetch_entity_sources
    try:
        result = await answer_question("习近平", model_id="x", llm_caller=mock_llm)
    finally:
        qa_mod.fetch_subgraph = orig_subgraph
        qa_mod.fetch_entity_sources = orig_sources

    assert result["status"] == "ok"
    assert result["sources"] != [], "sources 应包含引用文章"
    assert len(result["sources"]) == 2
    article_ids = {s["article_id"] for s in result["sources"]}
    assert article_ids == {"a1", "a2"}


@pytest.mark.asyncio
async def test_answer_question_dedupes_sources_across_entities():
    """同一文章被多个实体引用时,只出现一次"""
    async def mock_llm(prompt, **kwargs):
        if "JSON 数组" in prompt:
            return (
                '[{"name": "习近平", "type": "PERSON"},'
                '{"name": "党中央", "type": "ORGANIZATION"}]'
            )
        return "..."

    async def mock_fetch_subgraph(names, depth=2, limit=50):
        return {"nodes": [], "edges": []}

    # 两个实体都返回同一篇文章
    async def mock_fetch_entity_sources(name, db=None, limit=5):
        return [
            {"article_id": "shared", "title": "共享文章", "snippet": "...",
             "highlight_positions": []},
        ]

    from app.services.kg import qa as qa_mod
    orig_subgraph = qa_mod.fetch_subgraph
    orig_sources = qa_mod.fetch_entity_sources
    qa_mod.fetch_subgraph = mock_fetch_subgraph
    qa_mod.fetch_entity_sources = mock_fetch_entity_sources
    try:
        result = await answer_question("?", model_id="x", llm_caller=mock_llm)
    finally:
        qa_mod.fetch_subgraph = orig_subgraph
        qa_mod.fetch_entity_sources = orig_sources

    article_ids = [s["article_id"] for s in result["sources"]]
    assert len(article_ids) == 1
    assert article_ids[0] == "shared"
