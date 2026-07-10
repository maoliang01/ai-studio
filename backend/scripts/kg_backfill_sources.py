"""回溯老实体节点的 source_articles 字段"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.kg import Neo4jService  # noqa: E402
from app.core.database import get_session_local  # noqa: E402
from app.models.article import Article  # noqa: E402


async def backfill() -> dict:
    neo4j = Neo4jService()
    await neo4j.connect()
    try:
        async with neo4j._driver.session() as s:
            r = await s.run(
                "MATCH (e:Entity) WHERE e.entity_type IS NOT NULL "
                "RETURN e.name AS name, e.source_articles AS old"
            )
            rows = await r.data()

        db = get_session_local()()
        try:
            arts = db.query(Article).all()
        finally:
            db.close()

        updated = 0
        async with neo4j._driver.session() as s:
            for row in rows:
                name = row["name"]
                old = row["old"] or []
                if old or not name or len(name) < 2:
                    continue
                hits = []
                for a in arts:
                    text = (a.content or "") + " " + (a.summary or "")
                    if name in text:
                        hits.append(str(a.id))
                    if len(hits) >= 50:
                        break
                if hits:
                    await s.run(
                        "MATCH (e:Entity {name:$n}) SET e.source_articles = $ids",
                        n=name, ids=hits,
                    )
                    updated += 1
        return {"scanned": len(rows), "updated": updated}
    finally:
        await neo4j.close()


async def main():
    result = await backfill()
    print(f"扫描实体: {result['scanned']}")
    print(f"回溯更新: {result['updated']}")


if __name__ == "__main__":
    asyncio.run(main())
