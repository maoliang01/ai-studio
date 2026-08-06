"""
测试 kg_sync 编排服务
依赖 SQLite 测试 DB + Neo4j,通过 monkeypatch 隔离
"""
import os
import uuid
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import BackgroundTasks

from app.services.kg_sync import (
    on_article_created,
    on_article_updated,
    on_article_deleted,
    extract_and_link_entities,
    _extract_and_link_entities_inner,
    reconcile,
    recover_interrupted_articles,
)


@pytest.fixture
def mock_neo4j():
    """Mock Neo4jService 的方法"""
    with patch("app.services.kg_sync.build_neo4j") as build:
        instance = MagicMock()
        instance.upsert_article_metadata = AsyncMock(return_value=True)
        instance.delete_article_full = AsyncMock(return_value=True)
        instance.clear_article_knowledge = AsyncMock(return_value=True)
        instance.close = AsyncMock(return_value=None)
        instance.cleanup_orphan_entities = AsyncMock(return_value=0)
        instance.backfill_article_entity_sources = AsyncMock(return_value=0)
        instance.find_orphan_articles = AsyncMock(return_value=[])
        instance.find_dirty_articles = AsyncMock(return_value=[])
        instance._get_kg_article_ids = AsyncMock(return_value=set())
        instance._get_kg_content_hash = AsyncMock(return_value="")
        instance.batch_create_entities_and_relations = AsyncMock(
            return_value={"entities_created": 0, "relations_created": 0}
        )
        build.return_value = instance
        yield instance


@pytest.fixture
def mock_extractor():
    with patch("app.services.kg_sync.EntityExtractor") as Mock:
        instance = Mock.return_value
        result = MagicMock()
        result.error = None
        result.entities = []
        result.relations = []
        instance.extract = AsyncMock(return_value=result)
        instance.deduplicate_entities = MagicMock(return_value=[])
        yield instance


@pytest.fixture
def article():
    a = MagicMock()
    a.id = f"art-{uuid.uuid4()}"
    a.title = "T"
    a.url = "http://x"
    a.summary = "S"
    a.content = "C"
    a.content_hash = "h1"
    a.kg_status = "pending"
    a.kg_content_hash = None
    a.kg_error_message = None
    a.kg_processed_at = None
    return a


def test_recover_interrupted_articles_marks_processing_pending():
    db = MagicMock()
    db.query.return_value.filter.return_value.update.return_value = 2

    recovered = recover_interrupted_articles(db)

    assert recovered == 2
    db.query.return_value.filter.return_value.update.assert_called_once()
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_extraction_failure_preserves_existing_graph(article, mock_neo4j):
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = article
    failed_result = MagicMock(error="invalid JSON")

    with patch("app.services.kg_sync.get_session_local", return_value=lambda: session), \
         patch("app.services.kg_sync.EntityExtractor") as extractor_class, \
         patch("app.services.knowledge_jobs.enqueue_article_enhancement"):
        extractor_class.return_value.extract = AsyncMock(return_value=failed_result)
        success = await _extract_and_link_entities_inner(article.id)

    assert success is True
    assert article.kg_status == "partial"
    assert "保留原有图谱" in article.kg_error_message
    mock_neo4j.upsert_article_metadata.assert_awaited_once()
    mock_neo4j.clear_article_knowledge.assert_not_awaited()
    mock_neo4j.batch_create_entities_and_relations.assert_not_awaited()


@pytest.mark.asyncio
async def test_on_article_created_syncs_metadata_and_schedules_extract(
    article, mock_neo4j, mock_extractor
):
    bg = MagicMock(spec=BackgroundTasks)
    await on_article_created(article, bg)

    # 1. 同步 metadata
    mock_neo4j.upsert_article_metadata.assert_awaited_once()
    call_kwargs = mock_neo4j.upsert_article_metadata.await_args.kwargs
    assert call_kwargs["article_id"] == article.id
    assert call_kwargs["content_hash"] == "h1"
    assert call_kwargs["kg_status"] == "pending"

    # 2. 后台任务排上
    bg.add_task.assert_called_once()
    assert bg.add_task.call_args.args[0].__name__ == "extract_and_link_entities"
    assert bg.add_task.call_args.args[1] == article.id


@pytest.mark.asyncio
async def test_on_article_created_neo4j_failure_does_not_raise(
    article, mock_extractor
):
    with patch("app.services.kg_sync.build_neo4j") as build:
        instance = MagicMock()
        instance.upsert_article_metadata = AsyncMock(return_value=False)
        build.return_value = instance
        bg = MagicMock(spec=BackgroundTasks)
        # 不应抛
        await on_article_created(article, bg)
        # 后台仍排上
        bg.add_task.assert_called_once()


@pytest.mark.asyncio
async def test_on_article_updated_only_metadata_when_hash_unchanged(
    article, mock_neo4j
):
    article.content_hash = "h1"
    article.kg_content_hash = "h1"
    article.kg_status = "success"
    bg = MagicMock(spec=BackgroundTasks)
    await on_article_updated(article, bg)

    mock_neo4j.upsert_article_metadata.assert_awaited_once()
    call_kwargs = mock_neo4j.upsert_article_metadata.await_args.kwargs
    # hash 没变,kg_status 保持 success
    assert call_kwargs["kg_status"] == "success"
    # 不排后台任务
    bg.add_task.assert_not_called()


@pytest.mark.asyncio
async def test_on_article_updated_marks_pending_when_hash_changed(
    article, mock_neo4j
):
    article.content_hash = "h2"
    article.kg_content_hash = "h1"
    article.kg_status = "success"
    bg = MagicMock(spec=BackgroundTasks)
    await on_article_updated(article, bg)

    call_kwargs = mock_neo4j.upsert_article_metadata.await_args.kwargs
    assert call_kwargs["kg_status"] == "pending"
    # 暂不排后台(等用户点"重抽")
    bg.add_task.assert_not_called()


@pytest.mark.asyncio
async def test_on_article_deleted_calls_delete_full(article, mock_neo4j):
    await on_article_deleted(article.id)
    mock_neo4j.delete_article_full.assert_awaited_once_with(article.id)


@pytest.mark.asyncio
async def test_reconcile_returns_summary(article, mock_neo4j):
    with patch("app.services.kg_sync._get_kg_article_ids") as fake_get_ids, \
         patch("app.services.kg_sync._get_kg_content_hash") as fake_get_hash:
        # KG 里没有任何文章 → 全部 missing
        fake_get_ids.return_value = set()
        fake_get_hash.return_value = ""

        session = MagicMock()
        session.query.return_value.filter.return_value.all.return_value = [article]
        session.query.return_value.filter.return_value.first.return_value = article

        result = await reconcile(apply=False, db=session)

        assert "missing_in_kg" in result
        assert "orphan_in_kg" in result
        assert "dirty_in_kg" in result
        # article 在 SQLite 但不在 KG → 计入 missing
        assert article.id in result["missing_in_kg"]
        assert result["orphan_in_kg"] == []
        assert result["dirty_in_kg"] == []
