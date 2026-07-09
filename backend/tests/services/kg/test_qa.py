import pytest
from app.services.kg.qa import answer_question, extract_entities_from_question


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
