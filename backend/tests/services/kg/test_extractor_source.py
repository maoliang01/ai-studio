import pytest
from unittest.mock import AsyncMock
from app.services.kg.extractor import EntityExtractor


@pytest.mark.asyncio
async def test_extract_populates_source_articles(monkeypatch):
    extractor = EntityExtractor()

    async def mock_chat(*args, **kwargs):
        return '{"entities": [{"name": "X", "type": "PERSON", "subtype": "SCIENTIST", "description": "x"}], "relationships": []}'

    monkeypatch.setattr("app.services.kg.extractor.llm_service.non_stream_chat", mock_chat)

    result = await extractor.extract(content="Some text about X.", article_id="art-abc-123")
    nodes = result.entities
    assert len(nodes) == 1
    assert nodes[0].source_articles == ["art-abc-123"]


@pytest.mark.asyncio
async def test_extract_without_article_id_keeps_none(monkeypatch):
    async def mock_chat(*args, **kwargs):
        return '{"entities": [{"name": "X", "type": "PERSON"}], "relationships": []}'
    extractor = EntityExtractor()
    monkeypatch.setattr("app.services.kg.extractor.llm_service.non_stream_chat", mock_chat)
    result = await extractor.extract(content="X is here.")
    assert result.entities[0].source_articles is None


@pytest.mark.asyncio
async def test_extract_repairs_invalid_json_and_keeps_relation_evidence(monkeypatch):
    chat = AsyncMock(side_effect=[
        '{"entities": [{"name": "甲", "type": "PERSON"}] "relations": []}',
        '{"entities": [{"name": "甲", "type": "PERSON"}, '
        '{"name": "乙", "type": "ORGANIZATION"}], '
        '"relations": [{"source": "甲", "target": "乙", '
        '"rel_type": "part_of", "evidence": "甲加入乙", "confidence": 0.92}]}',
    ])
    monkeypatch.setattr(
        "app.services.kg.extractor.llm_service.non_stream_chat",
        chat,
    )

    result = await EntityExtractor().extract("甲加入乙", article_id="article-1")

    assert result.error is None
    assert chat.await_count == 2
    assert len(result.relations) == 1
    assert result.relations[0].properties == {
        "article_id": "article-1",
        "evidence": "甲加入乙",
        "confidence": 0.92,
    }


@pytest.mark.asyncio
async def test_extract_propagates_model_connection_error_without_repair(monkeypatch):
    chat = AsyncMock(return_value="[错误] Connection error.")
    monkeypatch.setattr(
        "app.services.kg.extractor.llm_service.non_stream_chat",
        chat,
    )

    result = await EntityExtractor().extract("测试文章")

    assert result.error == "模型调用失败: Connection error."
    assert chat.await_count == 1


def test_extract_json_object_handles_fenced_output():
    payload = EntityExtractor._extract_json_object(
        "说明\n```json\n{\"entities\": [], \"relations\": []}\n```"
    )

    assert payload == '{"entities": [], "relations": []}'
