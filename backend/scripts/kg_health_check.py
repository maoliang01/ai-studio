"""知识图谱数据健康评估脚本"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.kg import Neo4jService  # noqa: E402


def analyze(stats: Dict[str, Any], articles_in_kg: int) -> Dict[str, Any]:
    coverage = 0.0
    recs: List[str] = []
    if stats.get("total_relationships", 0) < stats.get("total_nodes", 0):
        recs.append("关系数少于节点数,存在孤立节点,建议补抽")
    if not stats.get("entities_by_subtype"):
        recs.append("未发现 subtype 细分,建议检查抽取 prompt 是否生效")
    return {
        "summary": {
            "total_nodes": stats.get("total_nodes", 0),
            "total_relationships": stats.get("total_relationships", 0),
            "articles_in_kg": articles_in_kg,
            "source_articles_coverage": coverage,
        },
        "entity_type_distribution": stats.get("entities_by_type", {}),
        "subtype_distribution": stats.get("entities_by_subtype", {}),
        "recommendations": recs,
    }


def write_report(report: Dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


async def main() -> None:
    neo4j = Neo4jService()
    await neo4j.connect()
    try:
        stats = await neo4j.get_graph_stats()
        async with neo4j._driver.session() as session:
            r = await session.run("MATCH (a:Article) RETURN count(a) AS c")
            articles_count = (await r.single())["c"]
            r2 = await session.run(
                """
                MATCH (e:Entity)
                WHERE e.entity_type IN $article_entity_types
                  AND e.source_articles IS NOT NULL
                  AND size(e.source_articles) > 0
                RETURN count(e) AS c
                """,
                article_entity_types=[
                    "PERSON", "ORGANIZATION", "LOCATION", "TECHNOLOGY",
                    "EVENT", "CONCEPT", "DATE",
                ],
            )
            covered = (await r2.single())["c"]
        article_entity_count = stats.get("article_entities", 0)
        coverage = covered / article_entity_count if article_entity_count else 0.0
        report = analyze(stats, articles_in_kg=articles_count)
        report["summary"]["source_articles_coverage"] = round(coverage, 4)
    finally:
        await neo4j.close()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = Path(f"reports/kg_health_{ts}.json")
    write_report(report, out_path)
    print(f"✓ 报告已生成: {out_path}")
    print(f"  总节点: {report['summary']['total_nodes']}")
    print(f"  关系数: {report['summary']['total_relationships']}")
    print(f"  实体-文章覆盖率: {report['summary']['source_articles_coverage'] * 100:.1f}%")
    for rec in report["recommendations"]:
        print(f"  ⚠ {rec}")


if __name__ == "__main__":
    asyncio.run(main())
