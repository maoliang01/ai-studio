import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_qa_answer_endpoint(monkeypatch):
    from app.api import kg as kg_api
    async def mock_answer(**kwargs):
        return {"status": "ok", "answer": "x", "subgraph": {"nodes": [], "edges": []}, "sources": [], "cited_entities": []}
    monkeypatch.setattr(kg_api, "answer_question", mock_answer)

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
