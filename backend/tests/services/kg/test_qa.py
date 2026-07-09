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
