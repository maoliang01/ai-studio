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
from app.services.kg.mining import (
    discover_alias_candidates,
    discover_causal_candidates,
    discover_historical_causal_claims,
    discover_transitive_inferences,
    build_spectral_embeddings,
    evaluate_embedding_quality,
    louvain_entity_communities,
    predict_structural_links,
    rank_embedding_similarities,
)

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


def build_review_id(review_type: str, source: str, target: str, rel_type: str = "") -> str:
    """Build a stable audit id for a mining decision."""
    endpoints = (source.strip(), target.strip())
    if review_type not in {"causal", "inference", "legacy_relation"}:
        endpoints = tuple(sorted(endpoints))
    left, right = endpoints
    raw = "\x1f".join((review_type.strip(), left, right, rel_type.strip()))
    return f"review-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]}"


def build_embedding_version(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    dimensions: int,
) -> str:
    node_signature = [
        f"node|{node['name']}|{node.get('entity_type') or ''}|{node.get('subtype') or ''}"
        for node in nodes
    ]
    edge_signature = [
        f"edge|{edge['source']}|{edge['target']}|{edge.get('weight', 1)}"
        for edge in edges
    ]
    digest = hashlib.sha256(
        "\n".join(sorted(node_signature + edge_signature)).encode("utf-8")
    ).hexdigest()[:12]
    return f"spectral-svd-v1-d{dimensions}-{digest}"


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

    async def execute(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        执行 Cypher 查询并返回结果列表

        参数：
        - query: Cypher 查询语句
        - params: 查询参数

        返回：
        - 结果记录列表
        """
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            result = await session.run(query, params or {})
            records = []
            async for record in result:
                records.append(dict(record))
            return records

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
                "CREATE CONSTRAINT mining_review_id IF NOT EXISTS FOR (r:MiningReview) REQUIRE r.id IS UNIQUE",
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

            await session.run(
                """
                MATCH ()-[r:RELATES_TO]->()
                SET r.provenance_status = CASE
                    WHEN r.provenance_status IN [
                        'recovered_evidence', 'reviewed_candidate', 'legacy_reviewed',
                        'inferred_reviewed', 'prediction_reviewed', 'causal_reviewed'
                    ] THEN r.provenance_status
                    WHEN size(coalesce(r.source_articles, [])) = 0 THEN 'legacy'
                    ELSE 'evidence_backed'
                END
                """
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

    async def create_entity(
        self,
        name: str,
        entity_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        创建实体节点（支持自定义属性）

        参数：
        - name: 实体名称
        - entity_type: 实体类型
        - properties: 自定义属性字典
        """
        if not self._driver:
            await self.connect()

        canonical_id = build_entity_id(name, entity_type)
        props = properties or {}

        async with self._driver.session() as session:
            query = """
            MERGE (e:Entity {name: $name})
            SET e.canonical_id = coalesce(e.canonical_id, $canonical_id),
                e.entity_type = $entity_type,
                e.updated_at = datetime()
            """
            # 动态添加属性
            for key, value in props.items():
                query += f"\n            SET e.{key} = ${key}"

            query += "\n            RETURN e"

            params = {
                "name": name,
                "canonical_id": canonical_id,
                "entity_type": entity_type,
            }
            params.update(props)

            try:
                await session.run(query, params)
                return True
            except Exception as e:
                logger.error(f"创建实体节点失败: {e}")
                return False

    async def create_relationship(
        self,
        source_name: str,
        target_name: str,
        relationship_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        创建两个实体之间的关系

        参数：
        - source_name: 源实体名称或ID
        - target_name: 目标实体名称或ID
        - relationship_type: 关系类型
        - properties: 关系属性
        """
        if not self._driver:
            await self.connect()

        props = properties or {}
        rel_id = props.get("id", f"rel_{source_name}_{target_name}")

        async with self._driver.session() as session:
            # 先尝试按 name 匹配，如果没有匹配则按 id 匹配
            query = f"""
            MATCH (a:Entity)
            WHERE a.name = $source_name OR a.id = $source_name
            WITH a
            MATCH (b:Entity)
            WHERE b.name = $target_name OR b.id = $target_name
            WITH a, b
            MERGE (a)-[r:{relationship_type}]->(b)
            SET r.id = $rel_id,
                r.updated_at = datetime()
            """

            for key, value in props.items():
                if key != "id":
                    query += f"\n            SET r.{key} = ${key}"

            query += "\n            RETURN r"

            params = {
                "source_name": source_name,
                "target_name": target_name,
                "rel_id": rel_id,
            }
            params.update({k: v for k, v in props.items() if k != "id"})

            try:
                await session.run(query, params)
                return True
            except Exception as e:
                logger.error(f"创建关系失败: {e}")
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
                r.provenance_status = CASE
                    WHEN $article_id IS NULL THEN coalesce(r.provenance_status, 'legacy')
                    ELSE 'evidence_backed'
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
                       coalesce(r.source_articles, []) AS source_articles,
                       coalesce(r.provenance_status, 'legacy') AS provenance_status
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
                evidence_samples: coalesce(rel.evidence_samples, []),
                provenance_status: coalesce(rel.provenance_status, 'legacy')
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

    async def get_alias_candidates(
        self,
        min_shared_articles: int = 2,
        min_score: float = 0.32,
        limit: int = 50,
        include_reviewed: bool = False,
    ) -> List[Dict[str, Any]]:
        """生成实体别名候选，仅供审查，不自动合并。"""
        if not self._driver:
            await self.connect()
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (e:Entity)
                OPTIONAL MATCH (a:Article)-[:CONTAINS_ENTITY]->(e)
                WITH e, collect(DISTINCT a.id) AS article_ids
                OPTIONAL MATCH (e)-[r:RELATES_TO]-(related:Entity)
                RETURN e.name AS name, e.canonical_id AS canonical_id,
                       e.entity_type AS entity_type, e.subtype AS subtype,
                       e.description AS description,
                       article_ids,
                       collect(DISTINCT {name: related.name, rel_type: r.rel_type}) AS related_entities
                """
            )
            entities = await result.data()
        candidates = discover_alias_candidates(
            entities,
            min_shared_articles=min_shared_articles,
            min_score=min_score,
            limit=limit,
        )
        reviews = await self.get_mining_reviews(review_type="alias", limit=1000)
        review_by_id = {
            review["id"]: review
            for review in reviews
            if review.get("status", "active") != "undone"
        }
        visible = []
        for candidate in candidates:
            review_id = build_review_id(
                "alias", candidate["left"]["name"], candidate["right"]["name"]
            )
            review = review_by_id.get(review_id)
            candidate["review"] = review
            if include_reviewed or not review:
                visible.append(candidate)
        return visible[:limit]

    async def get_mining_reviews(
        self,
        review_type: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Return persisted human decisions for mining candidates."""
        if not self._driver:
            await self.connect()
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (review:MiningReview)
                WHERE $review_type IS NULL OR review.review_type = $review_type
                RETURN review{.*} AS review
                ORDER BY review.reviewed_at DESC
                LIMIT $limit
                """,
                review_type=review_type,
                limit=max(1, min(int(limit), 2000)),
            )
            return [record["review"] for record in await result.data()]

    async def undo_mining_review(self, review_id: str) -> Dict[str, Any]:
        """Reverse a review effect while retaining its audit record."""
        if not self._driver:
            await self.connect()
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (review:MiningReview {id: $review_id})
                RETURN review{.*} AS review
                """,
                review_id=review_id,
            )
            record = await result.single()
            if not record:
                raise ValueError("review does not exist")
            review = record["review"]
            if review.get("status", "active") == "undone":
                raise ValueError("review has already been undone")

            review_type = review.get("review_type")
            decision = review.get("decision")
            if review_type == "alias" and decision == "approved":
                await session.run(
                    "MATCH ()-[rel:ALIAS_OF {review_id: $review_id}]->() DELETE rel",
                    review_id=review_id,
                )
            elif review_type == "cross_document" and decision == "approved":
                await session.run(
                    """
                    MATCH ()-[rel:RELATES_TO {review_id: $review_id}]->()
                    WHERE rel.provenance_status = 'reviewed_candidate'
                    DELETE rel
                    """,
                    review_id=review_id,
                )
            elif review_type == "inference" and decision == "approved":
                await session.run(
                    """
                    MATCH ()-[rel:RELATES_TO {review_id: $review_id}]->()
                    WHERE rel.provenance_status = 'inferred_reviewed'
                    DELETE rel
                    """,
                    review_id=review_id,
                )
            elif review_type == "link_prediction" and decision == "approved":
                await session.run(
                    """
                    MATCH ()-[rel:RELATES_TO {review_id: $review_id}]->()
                    WHERE rel.provenance_status = 'prediction_reviewed'
                    DELETE rel
                    """,
                    review_id=review_id,
                )
            elif review_type == "causal" and decision == "approved":
                await session.run(
                    """
                    MATCH ()-[rel:RELATES_TO {review_id: $review_id}]->()
                    WHERE rel.provenance_status = 'causal_reviewed'
                    DELETE rel
                    """,
                    review_id=review_id,
                )
            elif review_type == "legacy_relation" and decision == "kept":
                await session.run(
                    """
                    MATCH ()-[rel:RELATES_TO {review_id: $review_id}]->()
                    SET rel.provenance_status = $provenance_status,
                        rel.updated_at = datetime()
                    REMOVE rel.review_id
                    """,
                    review_id=review_id,
                    provenance_status=review.get("snapshot_provenance_status") or "legacy",
                )
            elif review_type == "legacy_relation" and decision == "deleted":
                await session.run(
                    """
                    MATCH (source:Entity {name: $source}), (target:Entity {name: $target})
                    MERGE (source)-[rel:RELATES_TO {rel_type: $rel_type}]->(target)
                    SET rel.confidence = $confidence,
                        rel.source_articles = $source_articles,
                        rel.evidence_samples = $evidence_samples,
                        rel.support_count = size($source_articles),
                        rel.provenance_status = $provenance_status,
                        rel.updated_at = datetime()
                    """,
                    source=review.get("source"),
                    target=review.get("target"),
                    rel_type=review.get("rel_type"),
                    confidence=review.get("snapshot_confidence") or 0.6,
                    source_articles=review.get("snapshot_source_articles") or [],
                    evidence_samples=review.get("snapshot_evidence_samples") or [],
                    provenance_status=review.get("snapshot_provenance_status") or "legacy",
                )

            updated = await session.run(
                """
                MATCH (review:MiningReview {id: $review_id})
                SET review.status = 'undone', review.undone_at = datetime()
                RETURN review{.*} AS review
                """,
                review_id=review_id,
            )
            updated_record = await updated.single()
            return updated_record["review"]

    async def review_alias_candidate(
        self,
        source: str,
        target: str,
        decision: str,
        canonical_name: Optional[str] = None,
        note: str = "",
    ) -> Dict[str, Any]:
        """Approve an alias as ALIAS_OF or persist a rejection without merging nodes."""
        if decision not in {"approved", "rejected"}:
            raise ValueError("decision must be approved or rejected")
        if not self._driver:
            await self.connect()
        canonical = canonical_name or source
        if canonical not in {source, target}:
            raise ValueError("canonical_name must be one of the candidate entities")
        alias = target if canonical == source else source
        review_id = build_review_id("alias", source, target)
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (source:Entity {name: $source}), (target:Entity {name: $target})
                MERGE (review:MiningReview {id: $review_id})
                SET review.review_type = 'alias', review.source = $source,
                    review.target = $target, review.decision = $decision,
                    review.original_decision = $decision, review.status = 'active',
                    review.canonical_name = $canonical_name, review.note = $note,
                    review.reviewed_at = datetime(), review.undone_at = null
                WITH review
                MATCH (alias:Entity {name: $alias}),
                      (canonical:Entity {name: $canonical_name})
                FOREACH (_ IN CASE WHEN $decision = 'approved' THEN [1] ELSE [] END |
                    MERGE (alias)-[rel:ALIAS_OF]->(canonical)
                    SET rel.review_id = $review_id, rel.status = 'approved',
                        rel.updated_at = datetime()
                )
                RETURN review{.*} AS review
                """,
                source=source,
                target=target,
                alias=alias,
                canonical_name=canonical,
                decision=decision,
                note=note[:500],
                review_id=review_id,
            )
            record = await result.single()
            if not record:
                raise ValueError("candidate entity does not exist")
            return record["review"]

    async def get_legacy_relations(self, limit: int = 500) -> List[Dict[str, Any]]:
        """返回尚无文章来源的历史关系，用于保守证据恢复。"""
        if not self._driver:
            await self.connect()
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (source:Entity)-[r:RELATES_TO]->(target:Entity)
                WHERE coalesce(r.provenance_status, 'legacy') = 'legacy'
                RETURN source.name AS source, target.name AS target,
                       r.rel_type AS rel_type, coalesce(r.confidence, 0.6) AS confidence,
                       source.source_articles AS source_article_ids,
                       target.source_articles AS target_article_ids
                LIMIT $limit
                """,
                limit=limit,
            )
            return await result.data()

    async def add_recovered_relation_evidence(
        self,
        source: str,
        target: str,
        rel_type: str,
        article_id: str,
        evidence: str,
        confidence: float = 0.6,
    ) -> bool:
        """为旧关系补入可追溯证据，并创建 status=recovered 的 Claim。"""
        if not self._driver:
            await self.connect()
        claim_id = build_claim_id(article_id, source, rel_type, target, evidence)
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (source:Entity {name: $source})
                      -[r:RELATES_TO {rel_type: $rel_type}]->
                      (target:Entity {name: $target})
                MATCH (article:Article {id: $article_id})
                SET r.source_articles = CASE
                        WHEN $article_id IN coalesce(r.source_articles, []) THEN r.source_articles
                        ELSE coalesce(r.source_articles, []) + $article_id
                    END,
                    r.evidence_samples = CASE
                        WHEN $evidence IN coalesce(r.evidence_samples, []) THEN r.evidence_samples
                        ELSE (coalesce(r.evidence_samples, []) + $evidence)[-5..]
                    END,
                    r.support_count = size(CASE
                        WHEN $article_id IN coalesce(r.source_articles, []) THEN r.source_articles
                        ELSE coalesce(r.source_articles, []) + $article_id
                    END),
                    r.provenance_status = 'recovered_evidence',
                    r.updated_at = datetime()
                MERGE (claim:Claim {id: $claim_id})
                SET claim.article_id = $article_id,
                    claim.rel_type = $rel_type,
                    claim.evidence = $evidence,
                    claim.confidence = $confidence,
                    claim.status = 'recovered',
                    claim.updated_at = datetime()
                MERGE (article)-[:ASSERTS]->(claim)
                MERGE (claim)-[:SUBJECT]->(source)
                MERGE (claim)-[:OBJECT]->(target)
                RETURN claim.id AS id
                """,
                source=source,
                target=target,
                rel_type=rel_type,
                article_id=article_id,
                evidence=evidence,
                confidence=max(0.0, min(float(confidence), 1.0)),
                claim_id=claim_id,
            )
            return await result.single() is not None

    async def review_legacy_relation(
        self,
        source: str,
        target: str,
        rel_type: str,
        decision: str,
        note: str = "",
    ) -> Dict[str, Any]:
        """Keep or delete an unsupported legacy relation with an audit snapshot."""
        if decision not in {"kept", "deleted"}:
            raise ValueError("decision must be kept or deleted")
        if not self._driver:
            await self.connect()
        review_id = build_review_id("legacy_relation", source, target, rel_type)
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (source:Entity {name: $source})
                      -[rel:RELATES_TO {rel_type: $rel_type}]->
                      (target:Entity {name: $target})
                WHERE coalesce(rel.provenance_status, 'legacy') = 'legacy'
                MERGE (review:MiningReview {id: $review_id})
                SET review.review_type = 'legacy_relation', review.source = $source,
                    review.target = $target, review.rel_type = $rel_type,
                    review.decision = $decision, review.original_decision = $decision,
                    review.status = 'active', review.note = $note,
                    review.snapshot_confidence = rel.confidence,
                    review.snapshot_source_articles = coalesce(rel.source_articles, []),
                    review.snapshot_evidence_samples = coalesce(rel.evidence_samples, []),
                    review.snapshot_provenance_status = coalesce(rel.provenance_status, 'legacy'),
                    review.reviewed_at = datetime(), review.undone_at = null
                FOREACH (_ IN CASE WHEN $decision = 'kept' THEN [1] ELSE [] END |
                    SET rel.provenance_status = 'legacy_reviewed',
                        rel.review_id = $review_id, rel.updated_at = datetime()
                )
                FOREACH (_ IN CASE WHEN $decision = 'deleted' THEN [1] ELSE [] END |
                    DELETE rel
                )
                RETURN review{.*} AS review
                """,
                source=source,
                target=target,
                rel_type=rel_type,
                decision=decision,
                note=note[:500],
                review_id=review_id,
            )
            record = await result.single()
            if not record:
                raise ValueError("legacy relation does not exist or has evidence")
            return record["review"]

    async def get_cross_document_candidates(
        self,
        min_shared_articles: int = 2,
        limit: int = 50,
        include_reviewed: bool = False,
    ) -> List[Dict[str, Any]]:
        """查找跨多篇文章稳定共现、但尚无显式关系的实体对。"""
        if not self._driver:
            await self.connect()
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (a:Article)-[:CONTAINS_ENTITY]->(left:Entity),
                      (a)-[:CONTAINS_ENTITY]->(right:Entity)
                WHERE elementId(left) < elementId(right)
                  AND left.entity_type <> 'DATE'
                  AND right.entity_type <> 'DATE'
                WITH left, right, collect(DISTINCT a.id) AS shared_articles
                WHERE size(shared_articles) >= $min_shared_articles
                  AND NOT (left)-[:RELATES_TO]-(right)
                WITH left, right, shared_articles,
                     size(coalesce(left.source_articles, [])) AS left_count,
                     size(coalesce(right.source_articles, [])) AS right_count
                RETURN left.name AS source, left.entity_type AS source_type,
                       right.name AS target, right.entity_type AS target_type,
                       shared_articles, size(shared_articles) AS support_count,
                       CASE WHEN left_count * right_count = 0 THEN 0.0
                            ELSE toFloat(size(shared_articles)) /
                                 sqrt(toFloat(left_count * right_count)) END AS score
                ORDER BY support_count DESC, score DESC
                LIMIT $limit
                """,
                min_shared_articles=min_shared_articles,
                limit=limit,
            )
            candidates = await result.data()
        reviews = await self.get_mining_reviews(review_type="cross_document", limit=1000)
        review_by_id = {
            review["id"]: review
            for review in reviews
            if review.get("status", "active") != "undone"
        }
        visible = []
        for candidate in candidates:
            review_id = build_review_id(
                "cross_document", candidate["source"], candidate["target"]
            )
            review = review_by_id.get(review_id)
            candidate["review"] = review
            if include_reviewed or not review:
                visible.append(candidate)
        return visible[:limit]

    async def review_cross_document_candidate(
        self,
        source: str,
        target: str,
        decision: str,
        note: str = "",
    ) -> Dict[str, Any]:
        """Persist a cross-document decision and optionally add a co-occurrence edge."""
        if decision not in {"approved", "rejected"}:
            raise ValueError("decision must be approved or rejected")
        if not self._driver:
            await self.connect()
        review_id = build_review_id("cross_document", source, target)
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (source:Entity {name: $source}), (target:Entity {name: $target})
                MATCH (article:Article)-[:CONTAINS_ENTITY]->(source),
                      (article)-[:CONTAINS_ENTITY]->(target)
                WITH source, target, collect(DISTINCT article.id) AS shared_articles
                WHERE size(shared_articles) >= 2
                MERGE (review:MiningReview {id: $review_id})
                SET review.review_type = 'cross_document', review.source = $source,
                    review.target = $target, review.decision = $decision,
                    review.original_decision = $decision, review.status = 'active',
                    review.note = $note, review.shared_articles = shared_articles,
                    review.support_count = size(shared_articles), review.reviewed_at = datetime(),
                    review.undone_at = null
                FOREACH (_ IN CASE WHEN $decision = 'approved' THEN [1] ELSE [] END |
                    MERGE (source)-[rel:RELATES_TO {rel_type: 'CO_OCCURS_WITH'}]->(target)
                    SET rel.source_articles = shared_articles,
                        rel.support_count = size(shared_articles),
                        rel.confidence = 1.0,
                        rel.evidence_samples = ['人工审核：跨文档共同出现'],
                        rel.provenance_status = 'reviewed_candidate',
                        rel.review_id = $review_id,
                        rel.updated_at = datetime()
                )
                RETURN review{.*} AS review
                """,
                source=source,
                target=target,
                decision=decision,
                note=note[:500],
                review_id=review_id,
            )
            record = await result.single()
            if not record:
                raise ValueError("candidate no longer satisfies cross-document criteria")
            return record["review"]

    async def get_communities(
        self,
        min_size: int = 3,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """读取图数据并执行确定性加权标签传播社区发现。"""
        if not self._driver:
            await self.connect()
        async with self._driver.session() as session:
            node_result = await session.run(
                """
                MATCH (e:Entity)
                OPTIONAL MATCH (a:Article)-[:CONTAINS_ENTITY]->(e)
                RETURN e.name AS name, e.canonical_id AS canonical_id,
                       e.entity_type AS entity_type, e.subtype AS subtype,
                       collect(DISTINCT a.id) AS article_ids
                """
            )
            nodes = await node_result.data()
            edge_result = await session.run(
                """
                MATCH (source:Entity)-[r:RELATES_TO]->(target:Entity)
                RETURN source.name AS source, target.name AS target,
                       r.rel_type AS rel_type,
                       CASE WHEN coalesce(r.support_count, 0) > 0
                            THEN toFloat(r.support_count)
                            ELSE coalesce(r.confidence, 0.5) END AS weight
                """
            )
            edges = await edge_result.data()
        return louvain_entity_communities(nodes, edges, min_size=min_size)[:limit]

    async def get_transitive_inferences(
        self,
        relation_types: Optional[List[str]] = None,
        max_hops: int = 3,
        limit: int = 100,
        include_reviewed: bool = False,
    ) -> List[Dict[str, Any]]:
        """Return explainable rule candidates derived only from evidenced relations."""
        if not self._driver:
            await self.connect()
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (source:Entity)-[rel:RELATES_TO]->(target:Entity)
                WHERE rel.provenance_status IN ['evidence_backed', 'recovered_evidence']
                  AND ($relation_types = [] OR rel.rel_type IN $relation_types)
                RETURN source.name AS source, target.name AS target,
                       rel.rel_type AS rel_type,
                       coalesce(rel.confidence, 0.6) AS confidence,
                       coalesce(rel.source_articles, []) AS source_articles,
                       coalesce(rel.evidence_samples, []) AS evidence_samples
                """,
                relation_types=relation_types or [],
            )
            edges = await result.data()
        candidates = discover_transitive_inferences(
            edges,
            relation_types=set(relation_types) if relation_types else None,
            max_hops=max_hops,
            limit=limit,
        )
        reviews = await self.get_mining_reviews(review_type="inference", limit=2000)
        active_review_ids = {
            review["id"]
            for review in reviews
            if review.get("status", "active") != "undone"
        }
        visible = []
        for candidate in candidates:
            review_id = build_review_id(
                "inference", candidate["source"], candidate["target"], candidate["rel_type"]
            )
            candidate["review_id"] = review_id
            if include_reviewed or review_id not in active_review_ids:
                visible.append(candidate)
        return visible[:limit]

    async def review_inference_candidate(
        self,
        source: str,
        target: str,
        rel_type: str,
        decision: str,
        note: str = "",
    ) -> Dict[str, Any]:
        """Persist an inference decision and optionally materialize the reviewed edge."""
        if decision not in {"approved", "rejected"}:
            raise ValueError("decision must be approved or rejected")
        candidates = await self.get_transitive_inferences(
            relation_types=[rel_type], max_hops=5, limit=2000, include_reviewed=True
        )
        candidate = next(
            (
                item for item in candidates
                if item["source"] == source and item["target"] == target
                and item["rel_type"] == rel_type
            ),
            None,
        )
        if not candidate:
            raise ValueError("inference candidate no longer exists")
        review_id = build_review_id("inference", source, target, rel_type)
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (source:Entity {name: $source}), (target:Entity {name: $target})
                MERGE (review:MiningReview {id: $review_id})
                SET review.review_type = 'inference', review.source = $source,
                    review.target = $target, review.rel_type = $rel_type,
                    review.decision = $decision, review.original_decision = $decision,
                    review.status = 'active', review.note = $note,
                    review.path = $path, review.confidence = $confidence,
                    review.source_articles = $source_articles,
                    review.rule = $rule, review.reviewed_at = datetime(),
                    review.undone_at = null
                FOREACH (_ IN CASE WHEN $decision = 'approved' THEN [1] ELSE [] END |
                    MERGE (source)-[rel:RELATES_TO {rel_type: $rel_type}]->(target)
                    SET rel.source_articles = $source_articles,
                        rel.support_count = size($source_articles),
                        rel.confidence = $confidence,
                        rel.evidence_samples = [$rule + '：' + reduce(text = '', item IN $path | text + CASE WHEN text = '' THEN '' ELSE ' → ' END + item)],
                        rel.provenance_status = 'inferred_reviewed',
                        rel.review_id = $review_id,
                        rel.updated_at = datetime()
                )
                RETURN review{.*} AS review
                """,
                source=source,
                target=target,
                rel_type=rel_type,
                decision=decision,
                note=note[:500],
                path=candidate["path"],
                confidence=candidate["confidence"],
                source_articles=candidate["source_articles"],
                rule=candidate["rule"],
                review_id=review_id,
            )
            record = await result.single()
            return record["review"]

    async def get_link_predictions(
        self,
        min_common_neighbors: int = 2,
        min_score: float = 0.2,
        limit: int = 100,
        include_reviewed: bool = False,
    ) -> List[Dict[str, Any]]:
        """Return explainable structural link candidates from evidenced graph edges."""
        if not self._driver:
            await self.connect()
        async with self._driver.session() as session:
            node_result = await session.run(
                "MATCH (e:Entity) RETURN e.name AS name, e.entity_type AS entity_type"
            )
            nodes = await node_result.data()
            edge_result = await session.run(
                """
                MATCH (source:Entity)-[rel:RELATES_TO]->(target:Entity)
                WHERE rel.provenance_status IN [
                    'evidence_backed', 'recovered_evidence', 'inferred_reviewed'
                ]
                RETURN source.name AS source, target.name AS target
                """
            )
            edges = await edge_result.data()
        candidates = predict_structural_links(
            nodes,
            edges,
            min_common_neighbors=min_common_neighbors,
            min_score=min_score,
            limit=limit,
        )
        reviews = await self.get_mining_reviews(review_type="link_prediction", limit=2000)
        active_review_ids = {
            review["id"]
            for review in reviews
            if review.get("status", "active") != "undone"
        }
        visible = []
        for candidate in candidates:
            review_id = build_review_id("link_prediction", candidate["source"], candidate["target"])
            candidate["review_id"] = review_id
            if include_reviewed or review_id not in active_review_ids:
                visible.append(candidate)
        return visible[:limit]

    async def review_link_prediction(
        self,
        source: str,
        target: str,
        decision: str,
        note: str = "",
    ) -> Dict[str, Any]:
        """Persist a structural prediction decision and optionally add a generic relation."""
        if decision not in {"approved", "rejected"}:
            raise ValueError("decision must be approved or rejected")
        candidates = await self.get_link_predictions(limit=2000, include_reviewed=True)
        candidate = next(
            (item for item in candidates if {item["source"], item["target"]} == {source, target}),
            None,
        )
        if not candidate:
            raise ValueError("link prediction candidate no longer exists")
        review_id = build_review_id("link_prediction", source, target)
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (source:Entity {name: $source}), (target:Entity {name: $target})
                MERGE (review:MiningReview {id: $review_id})
                SET review.review_type = 'link_prediction', review.source = $source,
                    review.target = $target, review.decision = $decision,
                    review.original_decision = $decision, review.status = 'active',
                    review.note = $note, review.score = $score,
                    review.common_neighbors = $common_neighbors,
                    review.reviewed_at = datetime(), review.undone_at = null
                FOREACH (_ IN CASE WHEN $decision = 'approved' THEN [1] ELSE [] END |
                    MERGE (source)-[rel:RELATES_TO {rel_type: 'predicted_related_to'}]->(target)
                    SET rel.confidence = $score,
                        rel.support_count = size($common_neighbors),
                        rel.source_articles = [],
                        rel.evidence_samples = ['人工确认结构预测，共同邻居：' + reduce(text = '', item IN $common_neighbors | text + CASE WHEN text = '' THEN '' ELSE '、' END + item)],
                        rel.provenance_status = 'prediction_reviewed',
                        rel.review_id = $review_id,
                        rel.updated_at = datetime()
                )
                RETURN review{.*} AS review
                """,
                source=source,
                target=target,
                decision=decision,
                note=note[:500],
                score=candidate["score"],
                common_neighbors=candidate["common_neighbors"],
                review_id=review_id,
            )
            record = await result.single()
            return record["review"]

    async def get_temporal_events(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Return event entities with article anchors, DATE markers, and temporal edges."""
        if not self._driver:
            await self.connect()
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (event:Entity {entity_type: 'EVENT'})
                OPTIONAL MATCH (article:Article)-[:CONTAINS_ENTITY]->(event)
                OPTIONAL MATCH (article)-[:CONTAINS_ENTITY]->(date:Entity {entity_type: 'DATE'})
                WITH event, collect(DISTINCT article.id) AS article_ids,
                     collect(DISTINCT date.name) AS date_markers
                OPTIONAL MATCH (event)-[rel:RELATES_TO]->(other:Entity)
                WHERE rel.rel_type IN ['precedes', 'succeeds']
                RETURN event.name AS name, event.subtype AS subtype,
                       event.description AS description, article_ids, date_markers,
                       collect(DISTINCT {
                           target: other.name, rel_type: rel.rel_type,
                           confidence: rel.confidence,
                           source_articles: coalesce(rel.source_articles, [])
                       }) AS temporal_relations
                ORDER BY event.name
                LIMIT $limit
                """,
                limit=limit,
            )
            return await result.data()

    async def generate_graph_embeddings(self, dimensions: int = 16) -> Dict[str, Any]:
        """Generate and persist versioned structural embeddings for all entities."""
        if not self._driver:
            await self.connect()
        dimensions = max(2, min(int(dimensions), 64))
        async with self._driver.session() as session:
            node_result = await session.run(
                """
                MATCH (entity:Entity)
                RETURN entity.name AS name, entity.entity_type AS entity_type,
                       entity.subtype AS subtype
                """
            )
            nodes = await node_result.data()
            edge_result = await session.run(
                """
                MATCH (source:Entity)-[rel:RELATES_TO]->(target:Entity)
                WHERE rel.provenance_status IN [
                    'evidence_backed', 'recovered_evidence', 'reviewed_candidate',
                    'inferred_reviewed', 'prediction_reviewed', 'causal_reviewed'
                ]
                RETURN source.name AS source, target.name AS target,
                       CASE WHEN coalesce(rel.support_count, 0) > 0
                            THEN toFloat(rel.support_count)
                            ELSE coalesce(rel.confidence, 0.5) END AS weight
                """
            )
            edges = await edge_result.data()
            embeddings = build_spectral_embeddings(nodes, edges, dimensions=dimensions)
            actual_dimensions = len(next(iter(embeddings.values()), []))
            version = build_embedding_version(nodes, edges, actual_dimensions)
            rows = [
                {"name": name, "embedding": vector}
                for name, vector in embeddings.items()
            ]
            await session.run(
                """
                UNWIND $rows AS row
                MATCH (entity:Entity {name: row.name})
                SET entity.graph_embedding = row.embedding,
                    entity.embedding_version = $version,
                    entity.embedding_generated_at = datetime()
                """,
                rows=rows,
                version=version,
            )
        return {
            "version": version,
            "dimensions": actual_dimensions,
            "entity_count": len(rows),
            "edge_count": len(edges),
        }

    async def get_graph_embedding_status(self) -> Dict[str, Any]:
        """Return embedding coverage and whether the graph changed after generation."""
        if not self._driver:
            await self.connect()
        async with self._driver.session() as session:
            node_result = await session.run(
                """
                MATCH (entity:Entity)
                RETURN entity.name AS name, entity.entity_type AS entity_type,
                       entity.subtype AS subtype,
                       entity.graph_embedding AS embedding,
                       entity.embedding_version AS version,
                       toString(entity.embedding_generated_at) AS generated_at
                """
            )
            nodes = await node_result.data()
            edge_result = await session.run(
                """
                MATCH (source:Entity)-[rel:RELATES_TO]->(target:Entity)
                WHERE rel.provenance_status IN [
                    'evidence_backed', 'recovered_evidence', 'reviewed_candidate',
                    'inferred_reviewed', 'prediction_reviewed', 'causal_reviewed'
                ]
                RETURN source.name AS source, target.name AS target,
                       CASE WHEN coalesce(rel.support_count, 0) > 0
                            THEN toFloat(rel.support_count)
                            ELSE coalesce(rel.confidence, 0.5) END AS weight
                """
            )
            edges = await edge_result.data()

        embedded_rows = [row for row in nodes if row.get("embedding")]
        versions = sorted({row.get("version") for row in embedded_rows if row.get("version")})
        dimensions = len(embedded_rows[0]["embedding"]) if embedded_rows else 0
        expected_version = build_embedding_version(nodes, edges, dimensions) if dimensions else None
        generated_values = sorted(
            row["generated_at"] for row in embedded_rows if row.get("generated_at")
        )
        return {
            "entity_count": len(nodes),
            "embedded_count": len(embedded_rows),
            "coverage": round(len(embedded_rows) / len(nodes), 4) if nodes else 0.0,
            "dimensions": dimensions,
            "versions": versions,
            "current_version": versions[-1] if len(versions) == 1 else None,
            "expected_version": expected_version,
            "stale": bool(nodes) and (
                len(embedded_rows) != len(nodes)
                or len(versions) != 1
                or versions[0] != expected_version
            ),
            "generated_at": generated_values[-1] if generated_values else None,
            "edge_count": len(edges),
        }

    async def evaluate_graph_embeddings(self, k: int = 5) -> Dict[str, Any]:
        """Evaluate current embeddings against direct evidence-backed neighbors."""
        if not self._driver:
            await self.connect()
        async with self._driver.session() as session:
            node_result = await session.run(
                """
                MATCH (entity:Entity)
                WHERE entity.graph_embedding IS NOT NULL
                RETURN entity.name AS name, entity.graph_embedding AS embedding
                """
            )
            node_rows = await node_result.data()
            edge_result = await session.run(
                """
                MATCH (source:Entity)-[rel:RELATES_TO]->(target:Entity)
                WHERE rel.provenance_status IN [
                    'evidence_backed', 'recovered_evidence', 'reviewed_candidate',
                    'inferred_reviewed', 'prediction_reviewed', 'causal_reviewed'
                ]
                RETURN source.name AS source, target.name AS target
                """
            )
            edges = await edge_result.data()
        embeddings = {row["name"]: row["embedding"] for row in node_rows}
        if not embeddings:
            raise ValueError("graph embeddings have not been generated")
        return evaluate_embedding_quality(embeddings, edges, k=k)

    async def clear_graph_embeddings(self) -> int:
        """Remove generated embeddings while leaving graph knowledge untouched."""
        if not self._driver:
            await self.connect()
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (entity:Entity)
                WHERE entity.graph_embedding IS NOT NULL
                WITH collect(entity) AS entities, count(entity) AS count
                FOREACH (entity IN entities |
                    REMOVE entity.graph_embedding, entity.embedding_version,
                           entity.embedding_generated_at
                )
                RETURN count
                """
            )
            record = await result.single()
            return int(record["count"]) if record else 0

    async def get_similar_entities(
        self,
        entity_name: str,
        limit: int = 20,
        same_type: bool = False,
        min_score: float = 0.0,
    ) -> Dict[str, Any]:
        """Return cosine-nearest entities from the current embedding version."""
        if not self._driver:
            await self.connect()
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (entity:Entity)
                WHERE entity.graph_embedding IS NOT NULL
                RETURN entity.name AS name, entity.entity_type AS entity_type,
                       entity.subtype AS subtype,
                       entity.graph_embedding AS embedding,
                       entity.embedding_version AS version
                """
            )
            rows = await result.data()
        if not any(row["name"] == entity_name for row in rows):
            raise ValueError("entity does not exist or embeddings have not been generated")
        versions = {row.get("version") for row in rows if row.get("version")}
        embeddings = {row["name"]: row["embedding"] for row in rows}
        node_by_name = {row["name"]: row for row in rows}
        return {
            "entity": entity_name,
            "version": sorted(versions)[-1] if versions else None,
            "results": rank_embedding_similarities(
                entity_name,
                embeddings,
                node_by_name,
                limit=limit,
                same_type=same_type,
                min_score=min_score,
            ),
        }

    async def get_causal_candidates(
        self,
        limit: int = 100,
        include_reviewed: bool = False,
        articles: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Discover causal candidates from Claims and historical article sentences."""
        if not self._driver:
            await self.connect()
        async with self._driver.session() as session:
            claim_result = await session.run(
                """
                MATCH (claim:Claim)-[:SUBJECT]->(source:Entity)
                MATCH (claim)-[:OBJECT]->(target:Entity)
                RETURN source.name AS source, target.name AS target,
                       claim.evidence AS evidence, claim.confidence AS confidence,
                       claim.article_id AS article_id
                """
            )
            claims = await claim_result.data()
            relation_result = await session.run(
                """
                MATCH (source:Entity)-[rel:RELATES_TO]->(target:Entity)
                WHERE rel.rel_type IN ['causes', 'enables']
                RETURN source.name AS source, target.name AS target,
                       rel.rel_type AS rel_type
                """
            )
            existing = {
                (row["source"], row["target"], row["rel_type"])
                for row in await relation_result.data()
            }
            if articles:
                article_ids = [str(article.get("id") or "") for article in articles]
                entity_result = await session.run(
                    """
                    MATCH (article:Article)-[:CONTAINS_ENTITY]->(entity:Entity)
                    WHERE article.id IN $article_ids
                    RETURN article.id AS article_id,
                           collect(DISTINCT {name: entity.name, entity_type: entity.entity_type}) AS entities
                    """,
                    article_ids=article_ids,
                )
                entities_by_article = {
                    row["article_id"]: row["entities"]
                    for row in await entity_result.data()
                }
                claims.extend(discover_historical_causal_claims(articles, entities_by_article))
        candidates = discover_causal_candidates(claims, existing_relations=existing, limit=limit)
        reviews = await self.get_mining_reviews(review_type="causal", limit=2000)
        active_review_ids = {
            review["id"] for review in reviews
            if review.get("status", "active") != "undone"
        }
        visible = []
        for candidate in candidates:
            review_id = build_review_id(
                "causal", candidate["source"], candidate["target"], candidate["rel_type"]
            )
            candidate["review_id"] = review_id
            if include_reviewed or review_id not in active_review_ids:
                visible.append(candidate)
        return visible[:limit]

    async def review_causal_candidate(
        self,
        source: str,
        target: str,
        rel_type: str,
        decision: str,
        note: str = "",
        articles: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Persist a causal decision and optionally materialize the reviewed edge."""
        if decision not in {"approved", "rejected"}:
            raise ValueError("decision must be approved or rejected")
        candidates = await self.get_causal_candidates(
            limit=2000,
            include_reviewed=True,
            articles=articles,
        )
        candidate = next(
            (
                item for item in candidates
                if item["source"] == source and item["target"] == target
                and item["rel_type"] == rel_type
            ),
            None,
        )
        if not candidate:
            raise ValueError("causal candidate no longer exists")
        review_id = build_review_id("causal", source, target, rel_type)
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (source:Entity {name: $source}), (target:Entity {name: $target})
                MERGE (review:MiningReview {id: $review_id})
                SET review.review_type = 'causal', review.source = $source,
                    review.target = $target, review.rel_type = $rel_type,
                    review.decision = $decision, review.original_decision = $decision,
                    review.status = 'active', review.note = $note,
                    review.confidence = $confidence,
                    review.source_articles = $source_articles,
                    review.evidence_samples = $evidence_samples,
                    review.markers = $markers,
                    review.discovery_sources = $discovery_sources,
                    review.reviewed_at = datetime(),
                    review.undone_at = null
                FOREACH (_ IN CASE WHEN $decision = 'approved' THEN [1] ELSE [] END |
                    MERGE (source)-[rel:RELATES_TO {rel_type: $rel_type}]->(target)
                    SET rel.confidence = $confidence,
                        rel.support_count = $support_count,
                        rel.source_articles = $source_articles,
                        rel.evidence_samples = $evidence_samples,
                        rel.discovery_sources = $discovery_sources,
                        rel.provenance_status = 'causal_reviewed',
                        rel.review_id = $review_id,
                        rel.updated_at = datetime()
                )
                RETURN review{.*} AS review
                """,
                source=source,
                target=target,
                rel_type=rel_type,
                decision=decision,
                note=note[:500],
                confidence=candidate["confidence"],
                source_articles=candidate["source_articles"],
                evidence_samples=candidate["evidence_samples"],
                markers=candidate["markers"],
                discovery_sources=candidate.get("discovery_sources", []),
                support_count=candidate["support_count"],
                review_id=review_id,
            )
            record = await result.single()
            return record["review"]

    async def get_causal_chains(
        self,
        source: Optional[str] = None,
        target: Optional[str] = None,
        max_hops: int = 4,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Explore directed paths made only from reviewed causal relationships."""
        if not self._driver:
            await self.connect()
        max_hops = max(1, min(int(max_hops), 6))
        query = f"""
            MATCH path = (source:Entity)-[rels:RELATES_TO*1..{max_hops}]->(target:Entity)
            WHERE all(rel IN rels WHERE rel.rel_type IN ['causes', 'enables']
                      AND rel.provenance_status = 'causal_reviewed')
              AND ($source IS NULL OR source.name = $source)
              AND ($target IS NULL OR target.name = $target)
              AND source <> target
            RETURN [node IN nodes(path) | {{
                       name: node.name, entity_type: node.entity_type,
                       subtype: node.subtype
                   }}] AS nodes,
                   [rel IN rels | {{
                       rel_type: rel.rel_type,
                       confidence: rel.confidence,
                       source_articles: coalesce(rel.source_articles, []),
                       evidence_samples: coalesce(rel.evidence_samples, [])
                   }}] AS relations,
                   length(path) AS hops
            ORDER BY hops, [node IN nodes(path) | node.name]
            LIMIT $limit
        """
        async with self._driver.session() as session:
            result = await session.run(
                query,
                source=source.strip() if source else None,
                target=target.strip() if target else None,
                limit=max(1, min(int(limit), 500)),
            )
            rows = await result.data()
        return [
            {
                "nodes": row["nodes"],
                "relations": row["relations"],
                "hops": row["hops"],
                "confidence": round(
                    min(
                        float(relation.get("confidence") or 0.6)
                        for relation in row["relations"]
                    ),
                    4,
                ),
            }
            for row in rows
        ]

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
