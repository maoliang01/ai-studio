import pytest
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
