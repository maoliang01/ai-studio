import pytest
from app.services.kg.graph import EntityNode, Neo4jService


@pytest.mark.asyncio
async def test_create_entity_node_merges_source_articles():
    neo4j = Neo4jService()
    await neo4j.connect()
    try:
        name = "__test_entity_src_articles__"
        async with neo4j._driver.session() as s:
            await s.run("MATCH (e:Entity {name:$n}) DETACH DELETE e", n=name)
        await neo4j.create_entity_node(name=name, entity_type="PERSON", source_articles=["art-1"])
        await neo4j.create_entity_node(name=name, entity_type="PERSON", source_articles=["art-2"])
        async with neo4j._driver.session() as s:
            r = await s.run("MATCH (e:Entity {name:$n}) RETURN e.source_articles AS sa", n=name)
            row = await r.single()
            sa = sorted(row["sa"] or [])
            assert "art-1" in sa and "art-2" in sa
    finally:
        await neo4j.close()


@pytest.mark.asyncio
async def test_create_entity_node_without_source_articles_ok():
    neo4j = Neo4jService()
    await neo4j.connect()
    try:
        assert await neo4j.create_entity_node(name="__test_no_src__", entity_type="PERSON") is True
        async with neo4j._driver.session() as s:
            await s.run("MATCH (e:Entity {name:$n}) DETACH DELETE e", n="__test_no_src__")
    finally:
        await neo4j.close()
