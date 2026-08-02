"""
Neo4j 图数据库服务

提供实体和关系的增删改查操作
"""
import os
import logging
import hashlib
import re
import unicodedata
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from neo4j import AsyncGraphDatabase, AsyncDriver, Record

logger = logging.getLogger("ai-studio")

# Neo4j 配置
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


@dataclass
class EntityNode:
    """实体节点"""
    name: str
    entity_type: str
    description: Optional[str] = None
    subtype: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    source_articles: Optional[List[str]] = None
    entity_id: Optional[str] = None


@dataclass
class Relationship:
    """关系边"""
    source: str
    target: str
    rel_type: str
    properties: Optional[Dict[str, Any]] = None


def build_entity_id(name: str, entity_type: str) -> str:
    """生成稳定实体标识；后续实体消歧可迁移 canonical_id 而不依赖展示名称。"""
    normalized = unicodedata.normalize("NFKC", name or "").casefold().strip()
    normalized = re.sub(r"[\s\-_·•]+", "", normalized)
    digest = hashlib.sha256(f"{entity_type.upper()}:{normalized}".encode("utf-8")).hexdigest()
    return f"ent-{digest[:24]}"


def build_claim_id(
    article_id: str,
    source: str,
    rel_type: str,
    target: str,
    evidence: str,
) -> str:
    raw = "\x1f".join([article_id, source, rel_type, target, evidence])
    return f"claim-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]}"


class Neo4jService:
    """Neo4j 图数据库服务"""

    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        self.uri = uri
        self.user = user
        self.password = password
        self._driver: Optional[AsyncDriver] = None

    async def connect(self) -> None:
        """建立数据库连接"""
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
            logger.info(f"Neo4j 连接已建立: {self.uri}")

    async def close(self) -> None:
        """关闭数据库连接"""
        if self._driver:
            await self._driver.close()
            self._driver = None
            logger.info("Neo4j 连接已关闭")

    async def verify_connection(self) -> bool:
        """验证连接是否正常"""
        try:
            if not self._driver:
                await self.connect()
            async with self._driver.session() as session:
                result = await session.run("RETURN 1 as test")
                await result.single()
            return True
        except Exception as e:
            logger.error(f"Neo4j 连接验证失败: {e}")
            return False

    async def init_schema(self) -> None:
        """初始化图谱模式（创建约束和索引）"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            # 创建唯一性约束
            constraints = [
                "CREATE CONSTRAINT article_id IF NOT EXISTS FOR (a:Article) REQUIRE a.id IS UNIQUE",
                "CREATE CONSTRAINT entity_name IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE",
                "CREATE CONSTRAINT entity_canonical_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.canonical_id IS UNIQUE",
                "CREATE CONSTRAINT claim_id IF NOT EXISTS FOR (c:Claim) REQUIRE c.id IS UNIQUE",
            ]
            # 创建索引
            indexes = [
                "CREATE INDEX article_title IF NOT EXISTS FOR (a:Article) ON (a.title)",
                "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.entity_type)",
                "CREATE INDEX entity_name_idx IF NOT EXISTS FOR (e:Entity) ON (e.name)",
                "CREATE INDEX claim_article_id IF NOT EXISTS FOR (c:Claim) ON (c.article_id)",
                "CREATE INDEX claim_rel_type IF NOT EXISTS FOR (c:Claim) ON (c.rel_type)",
            ]

            for cql in constraints + indexes:
                try:
                    await session.run(cql)
                except Exception as e:
                    # 忽略已存在的约束/索引错误
                    logger.debug(f"约束/索引创建: {e}")

            missing_result = await session.run(
                """
                MATCH (e:Entity)
                WHERE e.canonical_id IS NULL
                RETURN elementId(e) AS element_id, e.name AS name,
                       e.entity_type AS entity_type
                """
            )
            for record in await missing_result.data():
                canonical_id = build_entity_id(
                    record["name"] or "",
                    record["entity_type"] or "CONCEPT",
                )
                try:
                    await session.run(
                        """
                        MATCH (e:Entity)
                        WHERE elementId(e) = $element_id
                        SET e.canonical_id = $canonical_id,
                            e.canonical_name = coalesce(e.canonical_name, e.name)
                        """,
                        element_id=record["element_id"],
                        canonical_id=canonical_id,
                    )
                except Exception as e:
                    logger.warning(
                        "实体 canonical_id 回填冲突 name=%s: %s",
                        record["name"],
                        e,
                    )

            logger.info("Neo4j 模式初始化完成")

    async def create_article_node(
        self,
        article_id: str,
        title: str,
        url: str,
        summary: Optional[str] = None
    ) -> bool:
        """创建文章节点"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            query = """
            MERGE (a:Article {id: $article_id})
            SET a.title = $title,
                a.url = $url,
                a.summary = $summary,
                a.updated_at = datetime()
            RETURN a
            """
            try:
                await session.run(query, {
                    "article_id": article_id,
                    "title": title,
                    "url": url,
                    "summary": summary
                })
                return True
            except Exception as e:
                logger.error(f"创建文章节点失败: {e}")
                return False

    async def create_entity_node(
        self,
        name: str,
        entity_type: str,
        description: Optional[str] = None,
        subtype: Optional[str] = None,
        source_articles: Optional[List[str]] = None,
    ) -> bool:
        """创建实体节点(支持累积 source_articles)"""
        if not self._driver:
            await self.connect()

        new_articles = source_articles or []
        canonical_id = build_entity_id(name, entity_type)

        async with self._driver.session() as session:
            try:
                if new_articles:
                    # MERGE 后合并 source_articles 列表(去重)
                    query = """
                    MERGE (e:Entity {name: $name})
                    SET e.canonical_id = coalesce(e.canonical_id, $canonical_id),
                        e.canonical_name = coalesce(e.canonical_name, $name),
                        e.entity_type = $entity_type,
                        e.description = $description,
                        e.subtype = $subtype,
                        e.source_articles = REDUCE(acc = coalesce(e.source_articles, []), item IN $new_articles |
                            CASE WHEN item IN acc THEN acc ELSE acc + item END),
                        e.updated_at = datetime()
                    RETURN e
                    """
                    await session.run(query, {
                        "name": name,
                        "canonical_id": canonical_id,
                        "entity_type": entity_type,
                        "description": description or "",
                        "subtype": subtype or "",
                        "new_articles": new_articles,
                    })
                else:
                    query = """
                    MERGE (e:Entity {name: $name})
                    SET e.canonical_id = coalesce(e.canonical_id, $canonical_id),
                        e.canonical_name = coalesce(e.canonical_name, $name),
                        e.entity_type = $entity_type,
                        e.description = $description,
                        e.subtype = $subtype,
                        e.updated_at = datetime()
                    RETURN e
                    """
                    await session.run(query, {
                        "name": name,
                        "canonical_id": canonical_id,
                        "entity_type": entity_type,
                        "description": description or "",
                        "subtype": subtype or ""
                    })
                return True
            except Exception as e:
                logger.error(f"创建实体节点失败: {e}")
                return False

    async def link_article_to_entity(
        self,
        article_id: str,
        entity_name: str,
        confidence: float = 1.0
    ) -> bool:
        """建立文章与实体的关联"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            query = """
            MATCH (a:Article {id: $article_id})
            MATCH (e:Entity {name: $entity_name})
            MERGE (a)-[r:CONTAINS_ENTITY]->(e)
            SET r.confidence = $confidence,
                r.updated_at = datetime()
            RETURN r
            """
            try:
                await session.run(query, {
                    "article_id": article_id,
                    "entity_name": entity_name,
                    "confidence": confidence
                })
                return True
            except Exception as e:
                logger.error(f"建立文章-实体关联失败: {e}")
                return False

    async def link_entities(
        self,
        source_entity: str,
        target_entity: str,
        rel_type: str,
        confidence: float = 1.0,
        article_id: Optional[str] = None,
        evidence: str = "",
    ) -> bool:
        """建立带文章来源和证据的实体关系，并保留可审计 Claim。"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            claim_id = build_claim_id(
                article_id or "legacy",
                source_entity,
                rel_type,
                target_entity,
                evidence,
            )
            query = """
            MATCH (s:Entity {name: $source_entity})
            MATCH (t:Entity {name: $target_entity})
            MERGE (s)-[r:RELATES_TO {rel_type: $rel_type}]->(t)
            SET r.confidence = CASE
                    WHEN r.confidence IS NULL OR $confidence > r.confidence THEN $confidence
                    ELSE r.confidence
                END,
                r.source_articles = CASE
                    WHEN $article_id IS NULL THEN coalesce(r.source_articles, [])
                    WHEN $article_id IN coalesce(r.source_articles, []) THEN r.source_articles
                    ELSE coalesce(r.source_articles, []) + $article_id
                END,
                r.evidence_samples = CASE
                    WHEN $evidence = '' THEN coalesce(r.evidence_samples, [])
                    WHEN $evidence IN coalesce(r.evidence_samples, []) THEN r.evidence_samples
                    ELSE (coalesce(r.evidence_samples, []) + $evidence)[-5..]
                END,
                r.updated_at = datetime()
            SET r.support_count = size(coalesce(r.source_articles, []))
            WITH s, t, r
            OPTIONAL MATCH (a:Article {id: $article_id})
            FOREACH (_ IN CASE WHEN a IS NULL THEN [] ELSE [1] END |
                MERGE (c:Claim {id: $claim_id})
                SET c.article_id = $article_id,
                    c.rel_type = $rel_type,
                    c.evidence = $evidence,
                    c.confidence = $confidence,
                    c.status = 'asserted',
                    c.updated_at = datetime()
                MERGE (a)-[:ASSERTS]->(c)
                MERGE (c)-[:SUBJECT]->(s)
                MERGE (c)-[:OBJECT]->(t)
            )
            RETURN r
            """
            try:
                await session.run(query, {
                    "source_entity": source_entity,
                    "target_entity": target_entity,
                    "rel_type": rel_type,
                    "confidence": confidence,
                    "article_id": article_id,
                    "evidence": evidence,
                    "claim_id": claim_id,
                })
                return True
            except Exception as e:
                logger.error(f"建立实体关联失败: {e}")
                return False

    async def batch_create_entities_and_relations(
        self,
        article_id: str,
        entities: List[EntityNode],
        relations: List[Relationship]
    ) -> Dict[str, int]:
        """批量创建实体和关系"""
        if not self._driver:
            await self.connect()

        stats = {"entities_created": 0, "relations_created": 0}

        async with self._driver.session() as session:
            # 批量创建实体
            for entity in entities:
                success = await self.create_entity_node(
                    name=entity.name,
                    entity_type=entity.entity_type,
                    description=entity.description,
                    subtype=entity.subtype,
                    source_articles=entity.source_articles,
                )
                if success:
                    stats["entities_created"] += 1

            # 批量建立文章-实体关联
            for entity in entities:
                await self.link_article_to_entity(article_id, entity.name)

            # 批量建立实体间关系
            for rel in relations:
                success = await self.link_entities(
                    source_entity=rel.source,
                    target_entity=rel.target,
                    rel_type=rel.rel_type,
                    confidence=rel.properties.get("confidence", 1.0) if rel.properties else 1.0,
                    article_id=article_id,
                    evidence=rel.properties.get("evidence", "") if rel.properties else "",
                )
                if success:
                    stats["relations_created"] += 1

        return stats

    async def search_entities(
        self,
        query: Optional[str] = None,
        entity_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """搜索实体"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            if query:
                cql = """
                MATCH (e:Entity)
                WHERE e.name CONTAINS $query
                """
                params = {"query": query, "limit": limit}
            else:
                cql = "MATCH (e:Entity)"
                params = {"limit": limit}

            if entity_type:
                cql += " WHERE e.entity_type = $entity_type" if "WHERE" in cql else " AND e.entity_type = $entity_type"

            cql += " RETURN e ORDER BY e.name LIMIT $limit"

            try:
                result = await session.run(cql, params)
                records = await result.data()
                return [dict(record["e"]) for record in records]
            except Exception as e:
                logger.error(f"搜索实体失败: {e}")
                return []

    async def get_article_entities(self, article_id: str) -> List[Dict[str, Any]]:
        """获取文章关联的所有实体"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            query = """
            MATCH (a:Article {id: $article_id})-[:CONTAINS_ENTITY]->(e:Entity)
            RETURN e
            """
            try:
                result = await session.run(query, {"article_id": article_id})
                records = await result.data()
                return [dict(record["e"]) for record in records]
            except Exception as e:
                logger.error(f"获取文章实体失败: {e}")
                return []

    async def get_entity_profile(
        self,
        entity_name: str,
        neighbor_limit: int = 20,
        evidence_limit: int = 20,
    ) -> Optional[Dict[str, Any]]:
        """返回实体属性、跨文档来源、邻居和可审计关系证据。"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            entity_result = await session.run(
                """
                MATCH (e:Entity {name: $name})
                OPTIONAL MATCH (a:Article)-[:CONTAINS_ENTITY]->(e)
                RETURN e, collect(DISTINCT a.id) AS article_ids
                """,
                name=entity_name,
            )
            entity_record = await entity_result.single()
            if not entity_record:
                return None

            neighbor_result = await session.run(
                """
                MATCH (e:Entity {name: $name})-[r:RELATES_TO]-(n:Entity)
                RETURN n.name AS name, n.canonical_id AS canonical_id,
                       n.entity_type AS entity_type, n.subtype AS subtype,
                       r.rel_type AS rel_type, r.confidence AS confidence,
                       coalesce(r.support_count, 0) AS support_count,
                       coalesce(r.source_articles, []) AS source_articles
                ORDER BY support_count DESC, confidence DESC
                LIMIT $limit
                """,
                name=entity_name,
                limit=neighbor_limit,
            )
            neighbors = await neighbor_result.data()

            evidence_result = await session.run(
                """
                MATCH (c:Claim)-[:SUBJECT|OBJECT]->(e:Entity {name: $name})
                OPTIONAL MATCH (a:Article)-[:ASSERTS]->(c)
                OPTIONAL MATCH (c)-[:SUBJECT]->(s:Entity)
                OPTIONAL MATCH (c)-[:OBJECT]->(t:Entity)
                RETURN c.id AS claim_id, c.rel_type AS rel_type,
                       c.evidence AS evidence, c.confidence AS confidence,
                       c.status AS status, a.id AS article_id,
                       s.name AS source, t.name AS target
                ORDER BY c.confidence DESC
                LIMIT $limit
                """,
                name=entity_name,
                limit=evidence_limit,
            )
            evidence = await evidence_result.data()

        return {
            "entity": dict(entity_record["e"]),
            "article_ids": entity_record["article_ids"],
            "article_count": len(entity_record["article_ids"]),
            "neighbors": neighbors,
            "evidence": evidence,
        }

    async def find_shortest_paths(
        self,
        source_name: str,
        target_name: str,
        max_depth: int = 4,
        limit: int = 10,
        relation_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """查找受深度和关系类型约束的可解释最短路径。"""
        if not self._driver:
            await self.connect()

        max_depth = max(1, min(int(max_depth), 6))
        limit = max(1, min(int(limit), 20))
        query = f"""
        MATCH (source:Entity {{name: $source_name}}),
              (target:Entity {{name: $target_name}})
        MATCH path = allShortestPaths((source)-[:RELATES_TO*1..{max_depth}]-(target))
        WHERE $relation_types = [] OR
              all(rel IN relationships(path) WHERE rel.rel_type IN $relation_types)
        RETURN
            [node IN nodes(path) | {{
                name: node.name,
                canonical_id: node.canonical_id,
                entity_type: node.entity_type,
                subtype: node.subtype
            }}] AS nodes,
            [rel IN relationships(path) | {{
                source: startNode(rel).name,
                target: endNode(rel).name,
                rel_type: rel.rel_type,
                confidence: rel.confidence,
                support_count: coalesce(rel.support_count, 0),
                source_articles: coalesce(rel.source_articles, []),
                evidence_samples: coalesce(rel.evidence_samples, [])
            }}] AS relationships,
            length(path) AS length
        LIMIT $limit
        """
        async with self._driver.session() as session:
            result = await session.run(
                query,
                source_name=source_name,
                target_name=target_name,
                relation_types=relation_types or [],
                limit=limit,
            )
            return await result.data()

    async def get_entity_neighbors(
        self,
        entity_name: str,
        depth: int = 1
    ) -> List[Dict[str, Any]]:
        """获取实体的邻居节点和关系"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            query = f"""
            MATCH path = (e:Entity {{name: $entity_name}})-[r*1..{depth}]-(connected)
            UNWIND nodes(path) as node
            UNWIND relationships(path) as rel
            WITH collect(DISTINCT node) as nodes, collect(DISTINCT rel) as rels
            RETURN nodes, rels
            """
            try:
                result = await session.run(query, {"entity_name": entity_name})
                record = await result.single()
                if record:
                    nodes = [dict(n) for n in record["nodes"]]
                    rels = [dict(r) for r in record["rels"]]
                    return {"nodes": nodes, "relations": rels}
                return {"nodes": [], "relations": []}
            except Exception as e:
                logger.error(f"获取邻居节点失败: {e}")
                return {"nodes": [], "relations": []}

    async def get_graph_stats(self) -> Dict[str, int]:
        """获取图谱统计信息(含按 entity_type / subtype 分类)"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            stats = {}
            queries = {
                "articles": "MATCH (a:Article) RETURN count(a) as count",
                "entities": "MATCH (e:Entity) RETURN count(e) as count",
                "orphan_entities": "MATCH (e:Entity) WHERE NOT (e)<-[:CONTAINS_ENTITY]-(:Article) RETURN count(e) as count",
                "article_entity_links": "MATCH ()-[r:CONTAINS_ENTITY]->() RETURN count(r) as count",
                "entity_relations": "MATCH ()-[r:RELATES_TO]->() RETURN count(r) as count",
            }

            for key, cql in queries.items():
                try:
                    result = await session.run(cql)
                    record = await result.single()
                    stats[key] = record["count"] if record else 0
                except Exception as e:
                    logger.debug(f"统计查询 {key} 失败: {e}")
                    stats[key] = 0

            # 按 entity_type 分组
            try:
                r = await session.run("""
                    MATCH (e:Entity)
                    WHERE e.entity_type IS NOT NULL AND e.entity_type <> ''
                    RETURN e.entity_type AS t, count(e) AS c
                    ORDER BY c DESC
                """)
                rows = await r.data()
                stats["entities_by_type"] = {row["t"]: row["c"] for row in rows}
            except Exception as e:
                logger.debug(f"entities_by_type 统计失败: {e}")
                stats["entities_by_type"] = {}

            # 按 subtype 分组(细分领域)
            try:
                r = await session.run("""
                    MATCH (e:Entity)
                    WHERE e.subtype IS NOT NULL AND e.subtype <> ''
                    RETURN e.subtype AS s, count(e) AS c
                    ORDER BY c DESC
                """)
                rows = await r.data()
                stats["entities_by_subtype"] = {row["s"]: row["c"] for row in rows}
            except Exception as e:
                logger.debug(f"entities_by_subtype 统计失败: {e}")
                stats["entities_by_subtype"] = {}

            return stats

    async def delete_article_kg(self, article_id: str) -> bool:
        """删除文章关联的知识图谱数据（保留文章节点）"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            query = """
            MATCH (a:Article {id: $article_id})-[r:CONTAINS_ENTITY]->(e:Entity)
            DELETE r
            WITH a, e
            WHERE NOT (e)<-[:CONTAINS_ENTITY]-()
            DETACH DELETE e
            """
            try:
                await session.run(query, {"article_id": article_id})
                return True
            except Exception as e:
                logger.error(f"删除文章知识图谱失败: {e}")
                return False

    async def upsert_article_metadata(
        self,
        article_id: str,
        title: str,
        url: str,
        summary: Optional[str],
        content_hash: Optional[str],
        kg_status: str
    ) -> bool:
        """同步 Article 节点 metadata,不触发实体抽取"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            query = """
            MERGE (a:Article {id: $article_id})
            SET a.title = $title,
                a.url = $url,
                a.summary = $summary,
                a.content_hash = $content_hash,
                a.kg_status = $kg_status,
                a.updated_at = datetime()
            RETURN a
            """
            try:
                await session.run(query, {
                    "article_id": article_id,
                    "title": title,
                    "url": url,
                    "summary": summary or "",
                    "content_hash": content_hash or "",
                    "kg_status": kg_status
                })
                return True
            except Exception as e:
                logger.error(f"upsert_article_metadata 失败 {article_id}: {e}")
                return False

    async def delete_article_full(self, article_id: str) -> bool:
        """彻底删除文章节点及其实体、Claim 和关系证据贡献。"""
        if not self._driver:
            await self.connect()

        if not await self.clear_article_knowledge(article_id):
            return False

        async with self._driver.session() as session:
            query = """
            MATCH (a:Article {id: $article_id})
            DETACH DELETE a
            """
            try:
                await session.run(query, {"article_id": article_id})
            except Exception as e:
                logger.error(f"delete_article_full 失败 {article_id}: {e}")
                return False
        await self.cleanup_orphan_entities()
        return True

    async def clear_article_knowledge(self, article_id: str) -> bool:
        """清除一篇文章产生的知识，保留 Article 元数据节点供安全重抽。"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            try:
                await session.run(
                    """
                    MATCH (c:Claim {article_id: $article_id})
                    DETACH DELETE c
                    """,
                    article_id=article_id,
                )
                await session.run(
                    """
                    MATCH ()-[r:RELATES_TO]->()
                    WHERE $article_id IN coalesce(r.source_articles, [])
                    SET r.source_articles = [id IN r.source_articles WHERE id <> $article_id]
                    SET r.support_count = size(r.source_articles)
                    WITH r
                    WHERE r.support_count = 0
                    DELETE r
                    """,
                    article_id=article_id,
                )
                await session.run(
                    """
                    MATCH (a:Article {id: $article_id})-[r:CONTAINS_ENTITY]->(e:Entity)
                    DELETE r
                    SET e.source_articles = [id IN coalesce(e.source_articles, []) WHERE id <> $article_id]
                    """,
                    article_id=article_id,
                )
            except Exception as e:
                logger.error(f"clear_article_knowledge 失败 {article_id}: {e}")
                return False

        await self.cleanup_orphan_entities()
        return True

    async def cleanup_orphan_entities(self) -> int:
        """删除没有任何 Article 入边的 Entity，以及这些实体上的关系。"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            query = """
            MATCH (e:Entity)
            WHERE NOT (e)<-[:CONTAINS_ENTITY]-(:Article)
            WITH collect(e) AS entities, count(e) AS deleted
            UNWIND entities AS e
            DETACH DELETE e
            RETURN deleted
            """
            try:
                result = await session.run(query)
                record = await result.single()
                return int(record["deleted"]) if record else 0
            except Exception as e:
                logger.error(f"cleanup_orphan_entities 失败: {e}")
                return 0

    async def find_orphan_articles(self, sqlite_ids: set) -> list:
        """返回 Neo4j 中存在但不在 sqlite_ids 集合的 Article.id"""
        if not self._driver:
            await self.connect()

        if not sqlite_ids:
            sqlite_ids = {"__empty__"}  # 避免空集合 Cypher 报错

        async with self._driver.session() as session:
            query = """
            MATCH (a:Article)
            WHERE NOT a.id IN $sqlite_ids
            RETURN a.id AS id
            """
            try:
                result = await session.run(query, {"sqlite_ids": list(sqlite_ids)})
                records = await result.data()
                return [r["id"] for r in records]
            except Exception as e:
                logger.error(f"find_orphan_articles 失败: {e}")
                return []

    async def find_dirty_articles(self, article_pairs: list) -> list:
        """
        入参: [(article_id, sqlite_hash, kg_hash), ...]
        返回: sqlite_hash != kg_hash 的 article_id 列表
        """
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            query = """
            UNWIND $pairs AS p
            MATCH (a:Article {id: p[0]})
            WHERE a.content_hash IS NULL OR a.content_hash <> p[1]
            RETURN a.id AS id
            """
            try:
                result = await session.run(query, {
                    "pairs": [[aid, sh, kh] for aid, sh, kh in article_pairs]
                })
                records = await result.data()
                return [r["id"] for r in records]
            except Exception as e:
                logger.error(f"find_dirty_articles 失败: {e}")
                return []

    async def export_graph_data(self, limit: int = 1000) -> Dict[str, Any]:
        """导出图谱数据(用于可视化)
        - 节点的 type 字段:Article 节点 → "Article";Entity 节点 → entity_type 属性
          (这样前端 D3 的 colorMap 才会按 PERSON/TECHNOLOGY 等细分领域上色)
        - subtype 作为细分领域,放进 data 里供前端展示
        """
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            # 导出节点(同时取 entity_type 和 subtype)
            nodes_query = """
            MATCH (n) WHERE 'Article' IN labels(n) OR 'Entity' IN labels(n)
            RETURN n, labels(n) as labels
            LIMIT $limit
            """
            # 导出边
            edges_query = """
            MATCH ()-[r]->()
            WHERE type(r) IN ['CONTAINS_ENTITY', 'RELATES_TO']
            RETURN r, startNode(r) as source, endNode(r) as target
            LIMIT $limit
            """

            try:
                nodes_result = await session.run(nodes_query, {"limit": limit})
                nodes_records = await nodes_result.data()

                edges_result = await session.run(edges_query, {"limit": limit})
                edges_records = await edges_result.data()

                nodes = []
                for record in nodes_records:
                    node_dict = record["n"]
                    labels = record["labels"]
                    is_article = "Article" in labels
                    node_id = str(node_dict.get("id", "")) or node_dict.get("name", "")
                    if is_article:
                        # 文章节点:type 固定为 Article
                        node_type = "Article"
                    else:
                        # 实体节点:用 entity_type 属性(细分到 PERSON/TECHNOLOGY 等)
                        # 缺省回退到 label
                        node_type = node_dict.get("entity_type") or (
                            labels[0] if labels else "Entity"
                        )
                    nodes.append({
                        "id": node_id,
                        "label": node_dict.get("title", "") or node_dict.get("name", ""),
                        "type": node_type,
                        "data": node_dict
                    })

                edges = []
                for record in edges_records:
                    # Neo4j 返回的关系格式: (start_node, type, end_node) 元组
                    rel_tuple = record["r"]
                    if isinstance(rel_tuple, tuple) and len(rel_tuple) == 3:
                        source_dict, rel_type, target_dict = rel_tuple
                    else:
                        source_dict = record.get("source", {})
                        target_dict = record.get("target", {})
                        rel_type = rel_tuple.get("type", "RELATES_TO") if isinstance(rel_tuple, dict) else "RELATES_TO"

                    edges.append({
                        "source": str(source_dict.get("id", "")) or source_dict.get("name", ""),
                        "target": str(target_dict.get("id", "")) or target_dict.get("name", ""),
                        "type": rel_type,
                        "data": {"type": rel_type}
                    })

                return {"nodes": nodes, "edges": edges}
            except Exception as e:
                logger.error(f"导出图谱数据失败: {e}")
                return {"nodes": [], "edges": []}


# 全局服务实例
neo4j_service = Neo4jService()
