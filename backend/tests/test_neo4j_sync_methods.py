"""
测试 Neo4jService 的 KG 同步方法
需要本地起 Neo4j (bolt://localhost:7687, neo4j/password)
测试用临时唯一前缀,setUp 清空
"""
import os
import asyncio
import uuid
import pytest
import pytest_asyncio
from neo4j import AsyncGraphDatabase

from app.services.kg.graph import Neo4jService


NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


@pytest_asyncio.fixture
async def neo4j_service():
    """每个测试用独立的服务实例,teardown 清空所有节点"""
    svc = Neo4jService(uri=NEO4J_URI, user=NEO4J_USER, password=NEO4J_PASSWORD)
    await svc.connect()
    # 每次清空
    async with svc._driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
    yield svc
    async with svc._driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
    await svc.close()


@pytest.mark.asyncio
async def test_upsert_article_metadata_creates_node(neo4j_service):
    aid = f"test-{uuid.uuid4()}"
    ok = await neo4j_service.upsert_article_metadata(
        article_id=aid, title="T1", url="http://x", summary="S1",
        content_hash="h1", kg_status="pending"
    )
    assert ok is True

    async with neo4j_service._driver.session() as session:
        result = await session.run("MATCH (a:Article {id: $id}) RETURN a", id=aid)
        record = await result.single()
        assert record is not None
        node = record["a"]
        assert node["title"] == "T1"
        assert node["kg_status"] == "pending"
        assert node["content_hash"] == "h1"


@pytest.mark.asyncio
async def test_upsert_article_metadata_updates_existing(neo4j_service):
    aid = f"test-{uuid.uuid4()}"
    await neo4j_service.upsert_article_metadata(
        article_id=aid, title="T1", url="http://x", summary="S1",
        content_hash="h1", kg_status="pending"
    )
    await neo4j_service.upsert_article_metadata(
        article_id=aid, title="T2", url="http://y", summary="S2",
        content_hash="h2", kg_status="success"
    )
    async with neo4j_service._driver.session() as session:
        result = await session.run("MATCH (a:Article {id: $id}) RETURN a", id=aid)
        record = await result.single()
        node = record["a"]
        assert node["title"] == "T2"
        assert node["kg_status"] == "success"


@pytest.mark.asyncio
async def test_delete_article_full_removes_node_and_edges(neo4j_service):
    aid = f"test-{uuid.uuid4()}"
    eid = "Entity-1"
    # 建文章 + 实体 + 边
    async with neo4j_service._driver.session() as session:
        await session.run(
            "CREATE (a:Article {id: $aid, title: 'T', url: 'u', summary: 's'})",
            aid=aid
        )
        await session.run(
            "CREATE (e:Entity {name: $eid, entity_type: 'PERSON'})",
            eid=eid
        )
        await session.run("""
            MATCH (a:Article {id: $aid}), (e:Entity {name: $eid})
            MERGE (a)-[:CONTAINS_ENTITY]->(e)
        """, aid=aid, eid=eid)

    ok = await neo4j_service.delete_article_full(aid)
    assert ok is True

    async with neo4j_service._driver.session() as session:
        r1 = await session.run("MATCH (a:Article {id: $aid}) RETURN a", aid=aid)
        assert await r1.single() is None
        r2 = await session.run("MATCH (e:Entity {name: $eid}) RETURN e", eid=eid)
        assert await r2.single() is None  # 孤儿实体也清掉


@pytest.mark.asyncio
async def test_delete_article_full_keeps_shared_entities(neo4j_service):
    """如果 Entity 仍被其他文章引用,不删 Entity"""
    a1, a2 = f"a-{uuid.uuid4()}", f"a-{uuid.uuid4()}"
    eid = "shared-entity"
    async with neo4j_service._driver.session() as session:
        for aid in (a1, a2):
            await session.run(
                "CREATE (a:Article {id: $aid, title: 'T', url: 'u'})",
                aid=aid
            )
        await session.run(
            "CREATE (e:Entity {name: $eid, entity_type: 'PERSON'})",
            eid=eid
        )
        for aid in (a1, a2):
            await session.run("""
                MATCH (a:Article {id: $aid}), (e:Entity {name: $eid})
                MERGE (a)-[:CONTAINS_ENTITY]->(e)
            """, aid=aid, eid=eid)

    await neo4j_service.delete_article_full(a1)

    async with neo4j_service._driver.session() as session:
        r1 = await session.run("MATCH (a:Article {id: $a1}) RETURN a", a1=a1)
        assert await r1.single() is None
        r2 = await session.run("MATCH (e:Entity {name: $eid}) RETURN e", eid=eid)
        assert await r2.single() is not None  # 仍被 a2 引用,保留


@pytest.mark.asyncio
async def test_cleanup_orphan_entities_removes_article_entity_only_graph(neo4j_service):
    e1, e2 = f"orphan-{uuid.uuid4()}", f"orphan-{uuid.uuid4()}"
    async with neo4j_service._driver.session() as session:
        await session.run(
            "CREATE (e1:Entity {name: $e1, entity_type: 'ORGANIZATION'})"
            "-[:RELATES_TO]->"
            "(e2:Entity {name: $e2, entity_type: 'EVENT'})",
            e1=e1,
            e2=e2,
        )

    deleted = await neo4j_service.cleanup_orphan_entities()
    assert deleted == 2

    async with neo4j_service._driver.session() as session:
        r = await session.run("MATCH (e:Entity) RETURN count(e) AS c")
        row = await r.single()
    assert row["c"] == 0


@pytest.mark.asyncio
async def test_cleanup_orphan_entities_preserves_knowledge_points(neo4j_service):
    name = f"kp-{uuid.uuid4()}"
    async with neo4j_service._driver.session() as session:
        await session.run(
            "CREATE (:Entity {name: $name, entity_type: 'KnowledgePoint'})",
            name=name,
        )

    deleted = await neo4j_service.cleanup_orphan_entities()
    assert deleted == 0

    async with neo4j_service._driver.session() as session:
        r = await session.run("MATCH (e:Entity {name: $name}) RETURN e", name=name)
        assert await r.single() is not None


@pytest.mark.asyncio
async def test_backfill_article_entity_sources_is_non_destructive(neo4j_service):
    aid = f"a-{uuid.uuid4()}"
    eid = f"entity-{uuid.uuid4()}"
    async with neo4j_service._driver.session() as session:
        await session.run("CREATE (:Article {id: $aid})", aid=aid)
        await session.run(
            "CREATE (:Entity {name: $eid, entity_type: 'PERSON', description: 'keep'})",
            eid=eid,
        )
        await session.run(
            "MATCH (a:Article {id: $aid}), (e:Entity {name: $eid}) "
            "CREATE (a)-[:CONTAINS_ENTITY]->(e)",
            aid=aid,
            eid=eid,
        )

    updated = await neo4j_service.backfill_article_entity_sources()
    assert updated == 1

    async with neo4j_service._driver.session() as session:
        r = await session.run(
            "MATCH (e:Entity {name: $eid}) RETURN e.source_articles AS sources, e.description AS description",
            eid=eid,
        )
        row = await r.single()
        assert row["sources"] == [aid]
        assert row["description"] == "keep"


@pytest.mark.asyncio
async def test_find_orphan_articles(neo4j_service):
    a1, a2, a3 = f"a-{uuid.uuid4()}", f"a-{uuid.uuid4()}", f"a-{uuid.uuid4()}"
    async with neo4j_service._driver.session() as session:
        for aid in (a1, a2, a3):
            await session.run(
                "CREATE (a:Article {id: $aid, title: 'T'})",
                aid=aid
            )

    # SQLite 只有 a1, a2
    sqlite_ids = {a1, a2}
    orphans = await neo4j_service.find_orphan_articles(sqlite_ids)
    assert set(orphans) == {a3}


@pytest.mark.asyncio
async def test_find_dirty_articles(neo4j_service):
    a1, a2 = f"a-{uuid.uuid4()}", f"a-{uuid.uuid4()}"
    async with neo4j_service._driver.session() as session:
        await session.run(
            "CREATE (a:Article {id: $a1, content_hash: 'h1'})",
            a1=a1
        )
        await session.run(
            "CREATE (a:Article {id: $a2, content_hash: 'h2'})",
            a2=a2
        )

    # a1 hash 一致, a2 hash 不一致
    pairs = [(a1, "h1", "h1"), (a2, "h2-new", "h2")]
    dirty = await neo4j_service.find_dirty_articles(pairs)
    assert dirty == [a2] or set(dirty) == {a2}
